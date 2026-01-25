from services.musetalk_bridge_v2 import MuseTalkBridge
import os

def run_tuning():
    print("--- MuseTalk Quality Tuning Suite ---")
    
    # Setup
    bridge = MuseTalkBridge(gpu_id=0)
    audio = "static/audio/intro.mp3" # Use existing
    if not os.path.exists(audio):
        audio = "static/audio_cache/sample_en_US_JennyNeural.mp3" # Fallback
    
    image = "static/img/sarah_avatar.jpg"
    
    # Variations
    settings = [
        {"shift": 0, "desc": "Default"},
        {"shift": -10, "desc": "Up_10px"},
        {"shift": 10, "desc": "Down_10px"},
        {"shift": 5, "desc": "Down_5px"}
    ]
    
    for s in settings:
        shift = s["shift"]
        desc = s["desc"]
        out = f"static/video/tune_{desc}.mp4"
        print(f"\nGenerating: {desc} (Shift: {shift})")
        bridge.generate(audio, image, out, bbox_shift=shift)
        print(f"Saved: {out}")

if __name__ == "__main__":
    run_tuning()
