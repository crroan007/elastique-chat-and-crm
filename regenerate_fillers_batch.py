import asyncio
import edge_tts
import os
from services.musetalk_bridge_v2 import MuseTalkBridge

# --- CONFIG ---
TTS_VOICE = "en-US-AvaNeural"
MUSE_GPU = 0
IMAGE_PATH = "static/img/sarah_v2.png"

# --- BATCH LIST ---
BATCH = [
    {
        "name": "filler_idle",
        "audio_source": "static/audio/silence.mp3", # Created via FFmpeg
        "output": "static/fillers/filler_idle.mp4",
        "params": {"bbox_shift": 0}
    },
    {
        "name": "filler_question",
        "text": "Let me look into that question for you.",
        "output": "static/fillers/filler_question.mp4",
         "params": {"bbox_shift": 0}
    },
    {
        "name": "filler_thinking",
        "text": "Hmm, let me think about that.",
        "output": "static/fillers/filler_thinking.mp4",
         "params": {"bbox_shift": 0}
    }
]

async def batch_generate():
    print(f"--- Batch Generating Fillers (V2) ---")
    
    bridge = MuseTalkBridge(gpu_id=MUSE_GPU)
    
    for item in BATCH:
        print(f"\nProcessing: {item['name']}")
        output_path = item['output']
        
        # 1. Prepare Audio
        audio_path = ""
        if "audio_source" in item:
            audio_path = item['audio_source']
        elif "text" in item:
            audio_path = f"static/audio/{item['name']}.mp3"
            print(f"  Generating TTS: '{item['text']}'")
            communicate = edge_tts.Communicate(item['text'], TTS_VOICE)
            await communicate.save(audio_path)
        
        # 2. Generate Video
        print(f"  Driving Video -> {output_path}")
        # Synch call (removed await based on previous fix)
        bridge.generate(audio_path, IMAGE_PATH, output_path, bbox_shift=item['params']['bbox_shift'])
    
    print("\nBatch Complete.")

if __name__ == "__main__":
    asyncio.run(batch_generate())
