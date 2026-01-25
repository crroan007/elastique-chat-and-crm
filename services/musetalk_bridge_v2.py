import sys
import os
import shutil
import subprocess

# Global constants
coord_placeholder = (0.0, 0.0, 0.0, 0.0)
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
        print("DEBUG: Running V2 Bridge")
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
        
        # Avatar Cache
        self.avatar_cache = None
        
        # Initialize Audio Buffer for Streaming
        self.audio_buffer = bytearray()
        
        print("MuseTalk Bridge Initialized Successfully.")

    def load_avatar(self, image_path: str):
        """
        Pre-computes landmarks and VAE latents for the avatar to enable real-time streaming.
        """
        print(f"Loading Avatar: {image_path}")
        try:
            # TRY to import mmpose-based preprocessing, FALLBACK to MediaPipe
            try:
                from musetalk.utils.preprocessing import get_landmark_and_bbox
                # Check if it actually works or is a mock/broken
                # But import usually triggers the failure
            except (ImportError, ModuleNotFoundError):
                print("MMLab Missing in load_avatar. Using MediaPipe Fallback.")
                # We need to add CWD to path if services is local
                if os.getcwd() not in sys.path:
                    sys.path.append(os.getcwd())
                from services.landmark_utils import get_landmark_and_bbox
            
            from musetalk.models.vae import VAE
            import cv2
            
            image_path = os.path.abspath(image_path)
            
            # 1. Landmarks
            bbox_shift = 0
            coord_list, frame_list = get_landmark_and_bbox([image_path], bbox_shift)
            if not coord_list or len(coord_list) == 0:
                print("Error: No landmarks found for avatar.")
                return

            # 2. VAE Latents
            input_latent_list = []
            for bbox, frame in zip(coord_list, frame_list):
                 x1, y1, x2, y2 = bbox
                 y2 = min(bbox[3] + 10, frame.shape[0]) # Start with standard margin
                 crop_frame = frame[y1:y2, x1:x2]
                 crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
                 
                 with torch.no_grad():
                     latents = self.vae.get_latents_for_unet(crop_frame)
                 input_latent_list.append(latents)

            # Store in cache
            self.avatar_cache = {
                "frame": frame_list[0], # Base image (numpy),
                "coords": coord_list[0], # (x1, y1, x2, y2)
                "latents": input_latent_list[0], # Tensor
                "path": image_path
            }
            print(f"Avatar {image_path} Loaded & Cached.")
            
        except Exception as e:
            print(f"Avatar Load Failed: {e}")
            import traceback
            traceback.print_exc()

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
            from musetalk.models.vae import VAE
            from musetalk.models.unet import UNet, PositionalEncoding

            coord_placeholder = (0.0, 0.0, 0.0, 0.0)
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
            self.get_image = get_image
            # self.load_all_model was here but is not needed in generate()
            self.get_landmark_and_bbox = get_landmark_and_bbox
            
            # Helper for batch generation
            from musetalk.utils.utils import datagen
            self.get_landmark_and_bbox = get_landmark_and_bbox
            
            # Convert paths to absolute before context switch (which changes CWD)
            audio_path = os.path.abspath(audio_path)
            source_image_path = os.path.abspath(source_image_path)
            output_path = os.path.abspath(output_path)

            print(f"Generating animation for {audio_path} using {source_image_path}...")
            
            with ContextGuard(MUSE_TALK_PATH):
                # Lazy init FaceParsing inside context so it finds localized models
                if self.face_parser is None:
                     print("Initializing FaceParsing (Lazy, Context-Aware)...")
                     self.face_parser = FaceParsing(left_cheek_width=90, right_cheek_width=90)

                # --- 1. Audio Processing ---
                audio_res = self.audio_processor.get_audio_feature(audio_path)
                if audio_res is None:
                    print(f"ERROR: Audio Processor returned None for {audio_path}")
                    return None
                whisper_input_features, librosa_length = audio_res
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
                input_img_list = [source_image_path] # Single image list
                
                # Landmarks
                coord_list, frame_list = get_landmark_and_bbox(input_img_list, bbox_shift)
                
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
    
                frame_cycle = frame_list[0]
                coord_cycle = coord_list[0]
                latent_cycle = input_latent_list[0]
    
                # Create cycled lists matching audio chunks count
                input_latent_list_cycle = [latent_cycle] * max(1, len(whisper_chunks)) # Ensure it covers
    
                # --- 4. Inference Loop ---
                gen = datagen(
                    whisper_chunks=whisper_chunks,
                    vae_encode_latents=input_latent_list_cycle, 
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
                cmd_img2video = f'ffmpeg -y -v error -r {fps} -f image2 -i "{temp_frames_dir}/%08d.png" -vcodec libx264 -vf format=yuv420p -crf 18 "{temp_video_silent}"'
                print(f"Executing: {cmd_img2video}")
                os.system(cmd_img2video)
    
                # Combine Audio
                cmd_audio = f'ffmpeg -y -v error -i "{audio_path}" -i "{temp_video_silent}" -shortest "{output_path}"'
                print(f"Executing: {cmd_audio}")
                os.system(cmd_audio)
    
                # Cleanup
                if os.path.exists(temp_video_silent):
                    os.remove(temp_video_silent)
                shutil.rmtree(temp_frames_dir)
                
                return output_path
        
        except Exception as e:
            print(f"FAILED to run FFmpeg: {e}")
            import traceback
            traceback.print_exc()
            with open("gen_error.log", "w") as f:
                 f.write(f"Generate Error: {e}\n")
                 f.write(traceback.format_exc())
            return None

    def generate_stream_batch(self, audio_bytes: bytes, batch_size: int = 8):
        """
        Stream Generator (Perfect Sync Edition):
        1. Buffers Audio until > 2 frames (MIN_BATCH_SIZE).
        2. Generates video frames (N).
        3. Slices exactly N * 1920 bytes of audio.
        4. Yields (VideoFrame, AudioSlice) tuples.
        """
        # Yield nothing if unready
        if not self.is_ready or not self.avatar_cache:
            # print("Bridge Unready/NoAvatar - Yielding Nothing")
            return

        try:
            # 1. Update Buffer (Thread safety: GIL protects bytearray append?)
            # Pipecat is usually single-threaded consumer per pipeline.
            self.audio_buffer.extend(audio_bytes)

            # Define Minimum Batch (1 video frame = 1920 bytes @ 24kHz)
            # Use 3840 bytes (2 frames) for stability.
            MIN_BATCH_SIZE = 3840 
            
            # If buffer too small, yield nothing (Video stutters/holds)
            if len(self.audio_buffer) < MIN_BATCH_SIZE:
                 # print(f"DEBUG: Buffering... {len(self.audio_buffer)} / {MIN_BATCH_SIZE}")
                 return

            # Snapshot buffer for processing
            # We process everything we have to reduce latency
            process_chunk = self.audio_buffer[:] 
            
            # Create Temp File
            import tempfile
            import soundfile as sf
            
            # Windows Fix: Use delete=False and close manually.
            tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tf_path = tf.name
            tf.close() # CLOSE HANDLE IMMEDIATELY
            
            try:
                # Write Chunk
                audio_array = np.frombuffer(process_chunk, dtype=np.int16)
                # Resample check? No, sf.write writes as-is.
                sf.write(tf_path, audio_array, 24000)
                
                # 2. Extract Audio Features
                audio_res = self.audio_processor.get_audio_feature(tf_path)
                if audio_res is None:
                    return

                whisper_input_features, librosa_length = audio_res

                if len(whisper_input_features) == 0:
                    return
                
                # Use ContextGuard for Imports
                with ContextGuard(MUSE_TALK_PATH):
                    # Lazy Imports
                    from musetalk.utils.utils import datagen
                    from musetalk.models.vae import VAE
                    
                    # Robust Import for FaceParsing and Blending
                    FaceParsing = None
                    get_image = None
                    try:
                        from musetalk.utils.face_parsing import FaceParsing
                        from musetalk.utils.blending import get_image
                    except (ImportError, ModuleNotFoundError):
                        print("WARN: FaceParsing/MMPose missing. Using Simple Paste Fallback.")

                    # Ensure FaceParser if available (and enabled in self)
                    if FaceParsing and self.face_parser is None:
                         try:
                            self.face_parser = FaceParsing(left_cheek_width=90, right_cheek_width=90)
                         except:
                            print("WARN: FaceParsing init failed. Using Simple Paste Fallback.")
                            self.face_parser = None
                    
                    whisper_chunks = self.audio_processor.get_whisper_chunk(
                        whisper_input_features, 
                        self.device, 
                        self.unet.model.dtype, 
                        self.whisper, 
                        librosa_length,
                        fps=25,
                        audio_padding_length_left=2,
                        audio_padding_length_right=2
                    )
                    
                    # 3. Calculate Consumed Audio
                    total_frames = len(whisper_chunks)
                    BYTES_PER_FRAME = 1920 # 24kHz / 25fps * 2 bytes = 1920
                    bytes_consumed = total_frames * BYTES_PER_FRAME
                    
                    # Update Buffer: Remove ONLY the audio corresponding to generated frames
                    # This is CRITICAL for sync.
                    if bytes_consumed <= len(self.audio_buffer):
                         self.audio_buffer = self.audio_buffer[bytes_consumed:]
                    else:
                         # Should not happen unless mismatched calculation
                         self.audio_buffer = bytearray()

                    
                    # 4. Prepare Latents (Cycled)
                    latent_cycle = self.avatar_cache["latents"]
                    input_latent_list_cycle = [latent_cycle] * max(1, len(whisper_chunks))
                    
                    # 5. Inference Loop
                    gen = datagen(
                        whisper_chunks=whisper_chunks,
                        vae_encode_latents=input_latent_list_cycle, 
                        batch_size=batch_size,
                        delay_frame=0, # Real-time needs low latency
                        device=self.device
                    )
                    
                    # frame info
                    coord_cycle = self.avatar_cache["coords"]
                    frame_cycle = self.avatar_cache["frame"]
                    x1, y1, x2, y2 = coord_cycle
                    y2 = min(y2 + 10, frame_cycle.shape[0])
                    
                    for i, (whisper_batch, latent_batch) in enumerate(gen):
                        # Run Model
                        with torch.no_grad():
                            audio_feature_batch = self.pe(whisper_batch)
                            latent_batch = latent_batch.to(dtype=self.unet.model.dtype)
                            
                            pred_latents = self.unet.model(latent_batch, torch.tensor([0], device=self.device), encoder_hidden_states=audio_feature_batch).sample
                            recon = self.vae.decode_latents(pred_latents)
                        
                        # 6. Paste Back & Yield PAIRS
                        for k, res_frame in enumerate(recon):
                            # Calculate index in the *original process_chunk*
                            global_idx = (i * batch_size) + k
                            start_b = global_idx * BYTES_PER_FRAME
                            end_b = start_b + BYTES_PER_FRAME
                            
                            # Safely extract audio slice
                            if end_b <= len(process_chunk):
                                audio_slice = process_chunk[start_b:end_b]
                            else:
                                audio_slice = bytes([0] * BYTES_PER_FRAME) # Silence fallback

                            # Resize to crop
                            res_frame = cv2.resize(res_frame.astype(np.uint8), (x2-x1, y2-y1))
                            
                            if self.face_parser and get_image:
                                # Blend
                                combine_frame = get_image(frame_cycle, res_frame, [x1, y1, x2, y2], mode='jaw', fp=self.face_parser)
                            else:
                                # Simple Paste Fallback
                                combine_frame = frame_cycle.copy()
                                combine_frame[y1:y2, x1:x2] = res_frame
                            
                            # YIELD ATOMIC PAIR: (VideoFrame, AudioChunk)
                            yield (combine_frame, audio_slice)
                            
            except Exception as e:
                print(f"Bridge Inference Logic Error: {e}")
                # import traceback
                # traceback.print_exc()
                raise e
            finally:
                 # Cleanup Temp File
                 if os.path.exists(tf_path):
                     try:
                        os.unlink(tf_path)
                     except:
                        pass

        except Exception as e:
            print(f"Bridge Stream Error: {e}")
            raise e

    async def warmup(self):
        """
        Runs a dummy inference to initialize CUDA context and JIT compile models.
        This prevents the first user request from being slow.
        """
        if not self.is_ready:
            print("Bridge not ready, skipping warmup.")
            return

        print("WARMING UP MUSETALK ENGINE (Pre-Inference)...")
        try:
            # Dummy text
            text = "Warmup."
            # Dummy audio generation (fast)
            audio_path = "static/audio/silence.mp3" 
            if not os.path.exists(audio_path):
                # Ensure we wait for TTS if needed
                audio_path = await self.tts.generate_audio(text, "static/audio/warmup.mp3")
            
            # Using default avatar (sarah_v2.png) if not passed?
            # self.generate signature: audio_path, source_image_path, output_path
            # We need a source image.
            source_image_path = os.path.abspath("static/img/sarah_v2.png")
            
            output_path = os.path.abspath("static/generated/warmup.mp3") # MuseTalk appends video extension usually? No 
            output_path = os.path.abspath("static/generated/warmup.mp3.mp4") # Safer

            print(" > Running dummy generation cycle (Sync)...")
            
            # Run in executor to avoid blocking startup (though startup blocks anyway)
            import asyncio
            loop = asyncio.get_event_loop()
            
            # Use run_in_executor for the synchronous generate call
            # NOTE: generate returns output_path
            await loop.run_in_executor(
                None, 
                self.generate, 
                audio_path,
                source_image_path,
                output_path
            )

            print("WARMUP COMPLETE. Engine Ready.")
            
        except Exception as e:
            print(f"Warmup Warning (Non-Fatal): {e}")
            with open("gen_error.log", "w") as f:
                 f.write(f"Warmup Error: {e}\n")
                 f.write(traceback.format_exc())
            return None

# Simple Test
if __name__ == "__main__":
    print("--- MuseTalk Standalone Test V2 ---")
    
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
    output_test = "static/video/test_bridge_output_v2.mp4"
    
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
