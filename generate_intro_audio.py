import asyncio
import edge_tts

# Audio to Animate
TEXT = "Hello! I am Sarah. This is a real-time test of my new video avatar running on your RTX 50-90."
VOICE_ID = "en-US-AvaNeural"
OUTPUT_FILE = "intro.mp3"

async def gen_intro():
    print(f"Generating {OUTPUT_FILE}...")
    communicate = edge_tts.Communicate(TEXT, VOICE_ID)
    await communicate.save(OUTPUT_FILE)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(gen_intro())
