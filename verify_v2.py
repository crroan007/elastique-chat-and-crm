
import sys
import os
import traceback
from services.musetalk_bridge_v2 import MuseTalkBridge

LOG_FILE = "final_trace.txt"

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# Clean log
with open(LOG_FILE, "w") as f:
    f.write("--- START VERIFICATION ---\n")

try:
    log("Initializing Bridge...")
    bridge = MuseTalkBridge()
    log("Bridge Initialized.")
    
    test_audio = "static/audio/intro.mp3"
    # Find existing audio if intro misting
    if not os.path.exists(test_audio):
         cache_dir = "static/audio_cache"
         if os.path.exists(cache_dir):
            mp3s = [f for f in os.listdir(cache_dir) if f.endswith(".mp3")]
            if mp3s:
                test_audio = os.path.join(cache_dir, mp3s[0])
                log(f"Using cached audio: {test_audio}")
            else:
                raise FileNotFoundError("No audio file found")
         else:
             raise FileNotFoundError("static/audio_cache not found")

    test_image = "static/img/sarah_avatar.jpg"
    output_test = "static/video/test_bridge_output_v2.mp4"
    
    log(f"Generating video for {test_audio}...")
    result = bridge.generate(test_audio, test_image, output_test)
    
    if result:
        log(f"SUCCESS: {result}")
    else:
        log("FAILURE: generate returned None")
        
except Exception as e:
    log(f"CRITICAL ERROR: {e}")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        traceback.print_exc(file=f)

log("--- END VERIFICATION ---")
