import asyncio
import edge_tts
import os
from services.musetalk_bridge_v2 import MuseTalkBridge

async def generate_filler():
    print("--- Regenerating 'One Moment' Filler (V2) ---")
    
    # 1. Generate TTS
    text = "One moment please, let me check that."
    voice = "en-US-AvaNeural"
    audio_path = "static/audio/filler_temp.mp3"
    
    # Ensure dir
    os.makedirs("static/audio", exist_ok=True)
    
    print(f"Generating TTS: '{text}'")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(audio_path)
    
    # 2. Generate Video
    image_path = "static/img/sarah_v2.png"
    output_path = "static/fillers/filler_one_moment.mp4"
    
    print("Initializing MuseTalk...")
    bridge = MuseTalkBridge(gpu_id=0)
    
    if not os.path.exists(image_path):
        print("Error: Sarah V2 image missing.")
        return

    print(f"Generating Video -> {output_path}")
    bridge.generate(audio_path, image_path, output_path, bbox_shift=0)
    print("Filler Regeneration Complete.")

if __name__ == "__main__":
    asyncio.run(generate_filler())
