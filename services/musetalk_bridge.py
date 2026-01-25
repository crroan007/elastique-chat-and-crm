import sys
import os
import shutil
import asyncio
import cv2
import torch
import numpy as np
import pickle
from omegaconf import OmegaConf
from queue import Queue

# Add MuseTalk to path
MUSE_TALK_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../external/MuseTalk'))
print(f"Bridge MUSE_TALK_PATH: {MUSE_TALK_PATH}")
sys.path.append(MUSE_TALK_PATH)
from transformers import WhisperModel

class ContextGuard:
    def __init__(self, target_dir):
        self.target_dir = target_dir
        self.original_dir = os.getcwd()
    def __enter__(self):
        os.chdir(self.target_dir)
        sys.path.append(self.target_dir) # Ensure path is active
    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.original_dir)
        if self.target_dir in sys.path:
             sys.path.remove(self.target_dir)

class MuseTalkBridge:
    def __init__(self, 
                 unet_model_path=None, 
                 vae_type="sd-vae", 
                 unet_config=None,
                 whisper_dir=None,
                 gpu_id=0):
        
        self.device = torch.device(f"cuda:{gpu_id}" if torch.cuda.is_available() else "cpu")
        print("DEBUG: Running Patched Version 3894")
        print(f"Initializing MuseTalk on {self.device}...")

        # Paths
        base_model_dir = os.path.join(MUSE_TALK_PATH, "models")
        self.unet_model_path = unet_model_path or os.path.join(base_model_dir, "musetalkV15", "unet.pth")
        self.unet_config = unet_config or os.path.join(base_model_dir, "musetalkV15", "musetalk.json") # Default to v15 config
        self.whisper_dir = whisper_dir or os.path.join(base_model_dir, "whisper")
        
        # Flag to indicate if generation is possible
        self.is_ready = False

        # Load Models (Wrap in try/except for robustness)
        try:
            print("Loading VAE, UNet, and PE...")
            # Use ContextGuard to ensure relative paths in utils.py and models.py work (e.g. './models/...')
            with ContextGuard(MUSE_TALK_PATH):
                # Direct imports inside context
                from musetalk.utils.audio_processor import AudioProcessor
                from musetalk.utils.utils import get_file_type, get_video_fps, datagen, load_all_model

                if not load_all_model:
                     raise RuntimeError("MuseTalk modules not loaded. Cannot initialize bridge.")
        
                self.vae, self.unet, self.pe = load_all_model(
                    unet_model_path=self.unet_model_path,
                    vae_type=vae_type,
                    unet_config=self.unet_config,
                    device=self.device
                )
        
                # Move to device and half precision
                print("Optimizing models for RTX 5090 (Float16)...")
                self.pe = self.pe.half().to(self.device)
                self.vae.vae = self.vae.vae.half().to(self.device)
                self.unet.model = self.unet.model.half().to(self.device)
        
                # Initialize Audio Processor & Whisper
                print("Loading Whisper...")
                self.audio_processor = AudioProcessor(feature_extractor_path=self.whisper_dir)
                from transformers import WhisperModel
                self.whisper = WhisperModel.from_pretrained(self.whisper_dir)
                self.whisper = self.whisper.to(device=self.device, dtype=self.unet.model.dtype).eval()
                self.whisper.requires_grad_(False)
            
            self.is_ready = True
            print("MuseTalk Bridge Initialized Successfully (Models Loaded).")
            
        except Exception as e:
            print(f"MuseTalk Model Loading Failed: {e}")
            print("Bridge initialized in SAFE MODE. Generation will be disabled.")
            import traceback
            traceback.print_exc()
            with open("error.log", "w") as f:
                f.write(f"MuseTalk Model Loading Failed: {e}\n")
                f.write(traceback.format_exc())

        # Initialize Face Parser (Lazy Load)
        self.face_parser = None 
        
        print("MuseTalk Bridge Initialized Successfully.")

    def generate(self, 
                 audio_path: str, 
                 source_image_path: str, 
                 output_path: str,
                 fps: int = 25,
                 batch_size: int = 8,
                 bbox_shift: int = 0) -> str:
        """
        Generates a lip-synced video from a source image and audio.
        """
        if not self.is_ready:
             print("MuseTalk Bridge is NOT READY (Models failed to load). Skipping generation.")
             return None

        try:
            # Lazy loads to prevent circular/startup errors
            from musetalk.utils.blending import get_image
            from musetalk.utils.utils import load_all_model
            from musetalk.utils.face_parsing import FaceParsing # Still needed for blending

            # TRY to import mmpose-based preprocessing, FALLBACK to MediaPipe
            try:
                from musetalk.utils.preprocessing import get_landmark_and_bbox
                print("Using Original MuseTalk Preprocessing (MMLab)")
            except (ImportError, ModuleNotFoundError):
                print("MMLab Missing. Using MediaPipe Fallback for Landmarks.")
                # We need to add CWD to path if services is local
                import sys
                if os.getcwd() not in sys.path:
                    sys.path.append(os.getcwd())
                from services.landmark_utils import get_landmark_and_bbox
                
            self.get_image = get_image
            self.load_all_model = load_all_model # This is already imported globally, but keeping for consistency with user's intent
            self.get_landmark_and_bbox = get_landmark_and_bbox
            
            # Also mock the FaceParsing/Seg model if needed? 
            # MuseTalk uses FaceParsing from 'musetalk.utils.face_parsing' which usually requires 'resnet' weights.
            # That one is usually standard pytorch, not mmpose. So it might survive.
            
            if self.face_parser is None:
                 print("Initializing FaceParsing (Lazy)...")
                 self.face_parser = FaceParsing(left_cheek_width=90, right_cheek_width=90)

            # Convert paths to absolute before context switch (which changes CWD)
            audio_path = os.path.abspath(audio_path)
            source_image_path = os.path.abspath(source_image_path)
            output_path = os.path.abspath(output_path)

            print(f"Generating animation for {audio_path} using {source_image_path}...")
            
            with ContextGuard(MUSE_TALK_PATH):
                # --- 1. Audio Processing ---
                whisper_input_features, librosa_length = self.audio_processor.get_audio_feature(audio_path)
                whisper_chunks = self.audio_processor.get_whisper_chunk(
                    whisper_input_features, 
                    self.device, 
                    self.unet.model.dtype, 
                    self.whisper, 
                    librosa_length,
                    fps=fps,
                    audio_padding_length_left=2, # Default
                    audio_padding_length_right=2
                )
    
                # --- 2. Image Processing (One image -> Video frames) ---
                # Input is a single image, so we repeat it for the duration of the audio
                # But wait, MuseTalk expects input *frames*.
                # If we pass a single image, we need to treat it as a video of 1 frame repeated?
                # Or use logic from inference.py lines 127-129
                
                input_img_list = [source_image_path] # Single image list
                
                # Landmarks
                # We should cache landmarks for the avatar to avoid re-computing every time
                # For now, we compute.
                coord_list, frame_list = get_landmark_and_bbox(input_img_list, bbox_shift)
                
                # Since it's a single image, coord_list len is 1.
                # We need to cycle this for the animation.
                
                # --- 3. Latent Preparation ---
                input_latent_list = []
                for bbox, frame in zip(coord_list, frame_list):
                    if bbox == coord_placeholder:
                        continue
                    x1, y1, x2, y2 = bbox
                    # V15 extra margin logic
                    y2 = y2 + 10 # extra_margin default
                    y2 = min(y2, frame.shape[0])
                    
                    crop_frame = frame[y1:y2, x1:x2]
                    crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                    latents = self.vae.get_latents_for_unet(crop_frame)
                    input_latent_list.append(latents)
    
                # Cycle latency and frames for the video length
                # MuseTalk inference logic usually smooths start/end, but for real-time we just cycle
                # NOTE: frame_list[0] is the only frame
                frame_cycle = frame_list[0]
                coord_cycle = coord_list[0]
                latent_cycle = input_latent_list[0]
    
                # Create cycled lists matching audio chunks count
                # Actually datagen handles the cycling if we pass a list, but we only have 1 item.
                # Let's pass the single-item list and let datagen/loop unzip handle it?
                # datagen expects `vae_encode_latents` list.
                # In inference.py: input_latent_list_cycle = input_latent_list + input_latent_list[::-1]
                # Since we have 1 frame, it's just [latent, latent]
                input_latent_list_cycle = [latent_cycle] * max(1, len(whisper_chunks)) # Ensure it covers
    
                # --- 4. Inference Loop ---
                gen = datagen(
                    whisper_chunks=whisper_chunks,
                    vae_encode_latents=input_latent_list_cycle, # This might need to be longer or cycled inside datagen
                    batch_size=batch_size,
                    delay_frame=0,
                    device=self.device
                )
    
                res_frame_list = []
                total_batches = int(np.ceil(float(len(whisper_chunks)) / batch_size))
    
                for i, (whisper_batch, latent_batch) in enumerate(gen):
                    # Run Model
                    audio_feature_batch = self.pe(whisper_batch)
                    latent_batch = latent_batch.to(dtype=self.unet.model.dtype)
                    
                    pred_latents = self.unet.model(latent_batch, torch.tensor([0], device=self.device), encoder_hidden_states=audio_feature_batch).sample
                    recon = self.vae.decode_latents(pred_latents)
                    for res_frame in recon:
                        res_frame_list.append(res_frame)
    
                # --- 5. Paste Back & Save ---
                # Create a localized temp dir for frames
                temp_dir = os.path.dirname(output_path)
                temp_frames_dir = os.path.join(temp_dir, "temp_frames")
                os.makedirs(temp_frames_dir, exist_ok=True)
    
                for i, res_frame in enumerate(res_frame_list):
                    # Logic for single image paste back
                    bbox = coord_cycle
                    ori_frame = frame_cycle.copy()
                    x1, y1, x2, y2 = bbox
                    # V15 margin
                    y2 = y2 + 10
                    y2 = min(y2, ori_frame.shape[0])
    
                    try:
                        res_frame = cv2.resize(res_frame.astype(np.uint8), (x2-x1, y2-y1))
                        combine_frame = get_image(ori_frame, res_frame, [x1, y1, x2, y2], mode='jaw', fp=self.face_parser)
                        cv2.imwrite(f"{temp_frames_dir}/{str(i).zfill(8)}.png", combine_frame)
                    except Exception as e:
                        print(f"Frame {i} error: {e}")
                        continue
    
                # --- 6. FFMPEG Encode ---
                # Output video (silent)
                temp_video_silent = output_path.replace(".mp4", "_silent.mp4")
                
                # Use os.system for reliability with existing ffmpeg
                cmd_img2video = f"ffmpeg -y -v error -r {fps} -f image2 -i {temp_frames_dir}/%08d.png -vcodec libx264 -vf format=yuv420p -crf 18 {temp_video_silent}"
                os.system(cmd_img2video)
    
                # Combine Audio
                cmd_audio = f"ffmpeg -y -v error -i {audio_path} -i {temp_video_silent} -shortest {output_path}"
                os.system(cmd_audio)
    
                # Cleanup
                if os.path.exists(temp_video_silent):
                    os.remove(temp_video_silent)
                shutil.rmtree(temp_frames_dir)
                
                return output_path
        
        except Exception as e:
            print(f"MuseTalk Generation Failed: {e}")
            import traceback
            traceback.print_exc()
            return None

# Simple Test
if __name__ == "__main__":
    print("--- MuseTalk Standalone Test ---")
    
    # 1. Setup Paths
    test_audio = "static/audio/intro.mp3" 
    
    # Check if files exist
    if not os.path.exists(test_audio):
        print(f"Test Audio not found at {test_audio}. Searching audio_cache...")
        # Find first mp3 in audio_cache
        cache_dir = "static/audio_cache"
        if os.path.exists(cache_dir):
            mp3s = [f for f in os.listdir(cache_dir) if f.endswith(".mp3")]
            if mp3s:
                test_audio = os.path.join(cache_dir, mp3s[0])
                print(f"Using cached audio: {test_audio}")
            else:
                 print("No cached audio found.")
                 sys.exit(1)
        else:
             print("static/audio_cache not found.")
             sys.exit(1)
             
    test_image = "static/img/sarah_avatar.jpg"
    output_test = "static/video/test_bridge_output.mp4"
    
    if not os.path.exists(test_image):
        print(f"Test Image not found at {test_image}.")
        sys.exit(1)
        
    # 2. Initialize
    try:
        bridge = MuseTalkBridge()
        
        # 3. Generate
        print(f"Testing Generation...")
        result = bridge.generate(test_audio, test_image, output_test)
        
        if result and os.path.exists(result):
            print(f"SUCCESS: Video generated at {result}")
        else:
            print("FAILURE: Video generation returned None or file missing.")
            
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
