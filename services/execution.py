import os
import uuid
import subprocess
import edge_tts
import logging
from datetime import datetime
import time

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Execution")

# --- AUDIO ENGINE ---
async def generate_audio(text: str, voice: str = "en-US-AvaNeural"):
    """
    Generates TTS audio using edge-tts.
    Returns: (base64_string, file_path)
    """
    try:
        output_dir = "static/audio_cache"
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{uuid.uuid4()}.mp3"
        output_path = os.path.join(output_dir, filename)
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

        # Log TTS Input
        try:
             with open("server_conversation.txt", "a", encoding="utf-8") as f:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Sanitize text
                clean = text.replace("\n", " ").strip()
                f.write(f"{ts} | TTS_INPUT | {clean}\n")
        except Exception as e:
            logger.error(f"Failed to log TTS: {e}")
        
        # We don't strictly need b64 for the pipeline, but keeping signature compatible if needed
        # For now just returning path is enough for SadTalker
        return None, output_path
        
    except Exception as e:
        logger.error(f"TTS Generation Error: {e}")
        return None, None

# --- AVATAR ENGINE ---
def generate_avatar_video(audio_path: str, job_id: str = None):
    """
    Runs SadTalker inference on the audio file.
    Output: Path to the generated video (relative to static root) or None.
    """
    try:
        if not audio_path or not os.path.exists(audio_path):
            logger.error(f"Audio path invalid: {audio_path}")
            return None

        # Create Unique Job Directory
        if not job_id:
            job_id = f"job_{uuid.uuid4().hex}"
            
        result_dir = os.path.join("static", "generated", job_id)
        os.makedirs(result_dir, exist_ok=True)

        # Paths
        sadtalker_dir = "SadTalker"
        source_image = "static/sarah_avatar.jpg"
        
        abs_audio = os.path.abspath(audio_path)
        abs_image = os.path.abspath(source_image)
        abs_result = os.path.abspath(result_dir)
        
        # Command runs 'inference.py' directly, assuming CWD is sadtalker_dir
        command = [
            "python", "inference.py",
            "--driven_audio", abs_audio,
            "--source_image", abs_image,
            "--result_dir", abs_result,
            "--still", 
            "--preprocess", "crop",
            "--expression_scale", "1.0"
        ]
        
        logger.info(f"Starting SadTalker [{job_id}]... Audio: {audio_path}")
        subprocess.run(command, cwd=sadtalker_dir, check=True, capture_output=True)
        
        # Find the generated video in the UNIQUE result_dir
        # SadTalker may still create a subfolder timestamp inside our unique folder, or dump mp4 directly.
        # Check recursive.
        
        found_video = None
        for root, dirs, files in os.walk(result_dir):
            for file in files:
                if file.endswith(".mp4"):
                    found_video = os.path.join(root, file)
                    break
            if found_video:
                break
        
        if found_video:
            final_path = found_video.replace("\\", "/")
            logger.info(f"Video Generated [{job_id}]: {final_path}")
            return final_path
            
        logger.error(f"No video found in {result_dir} for job {job_id}")
        return None

    except Exception as e:
        logger.error(f"SadTalker Generation Error: {e}")
        return None

    except Exception as e:
        logger.error(f"SadTalker Generation Error: {e}")
        return None
