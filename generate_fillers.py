
import os
import asyncio
import shutil
import logging
from server import generate_audio, generate_avatar_video

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Longer, context-aware fillers (8-12 seconds)
FILLERS = [
    # GENERAL / COMPLEX
    {
        "filename": "filler_general_long",
        "text": "That is a truly excellent question. I want to make sure I give you the most accurate answer based on the latest clinical research, so please bear with me for just a moment while I synthesize that information."
    },
    # PRODUCT / PRICE
    {
        "filename": "filler_product_lookup",
        "text": "I would be happy to check our catalog for you. I am currently scanning our latest collection data to find the best options that match your specific needs. One moment please."
    },
    # MEDICAL / SCIENCE
    {
        "filename": "filler_science_deep",
        "text": "This involves some specific lymphatic mechanisms. I am cross-referencing your query with our scientific library to ensure I provide a medically precise explanation. Just a few seconds."
    }
]

async def create_fillers():
    output_dir = "static/fillers"
    os.makedirs(output_dir, exist_ok=True)

    for item in FILLERS:
        text = item["text"]
        fname = item["filename"]
        
        print(f"--- Generating Filler: {fname} ---")
        
        # 1. Audio
        b64, audio_path = await generate_audio(text)
        
        if not audio_path:
            logger.error(f"Failed to generate audio for {fname}")
            continue

        # 2. Video
        video_path = generate_avatar_video(audio_path)
        
        if video_path:
            # 3. Move/Rename
            final_path = os.path.join(output_dir, f"{fname}.mp4")
            if os.path.exists(final_path):
                os.remove(final_path)
            shutil.move(video_path, final_path)
            print(f"SUCCESS: Saved to {final_path}")
        else:
            logger.error(f"Failed to video for {fname}")

if __name__ == "__main__":
    asyncio.run(create_fillers())
