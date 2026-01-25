import asyncio
import os
from server import generate_audio

async def test_audio():
    print("Testing Audio Generation...")
    text = "Hello, this is a test of the Sarah Voice System."
    
    try:
        base64_audio = await generate_audio(text)
        if base64_audio:
            print(f"SUCCESS: Audio generated. Length: {len(base64_audio)} chars")
            # Save to file to manually check if needed
            with open("test_output.mp3", "wb") as f:
                import base64
                f.write(base64.decodebytes(base64_audio.encode('utf-8')))
            print("Saved test_output.mp3")
        else:
            print("FAILURE: generate_audio returned None")
    except Exception as e:
        print(f"FAILURE: Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_audio())
