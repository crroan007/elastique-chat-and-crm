from services.musetalk_bridge_v2 import MuseTalkBridge
import os

def regenerate_intro():
    print("--- Regenerating Intro Video with Sarah V2 ---")
    
    bridge = MuseTalkBridge(gpu_id=0)
    
    # Inputs - CORRECTION: intro.mp3 is in root
    audio_path = "intro.mp3"
    if not os.path.exists(audio_path):
        audio_path = "static/audio/intro.mp3"
        # Fallback to a TTS sample if dedicated intro missing
        audio_path = "static/audio_cache/sample_en_US_JennyNeural.mp3"
        
    image_path = "static/img/sarah_v2.png"
    output_path = "static/videos/intro_sarah.mp4"
    
    print(f"Audio: {audio_path}")
    print(f"Image: {image_path}")
    print(f"Output: {output_path}")
    
    if not os.path.exists(image_path):
        print("ERROR: New avatar image not found!")
        return

    bridge.generate(audio_path, image_path, output_path, bbox_shift=0)
    print("Intro Regeneration Complete.")

if __name__ == "__main__":
    regenerate_intro()
