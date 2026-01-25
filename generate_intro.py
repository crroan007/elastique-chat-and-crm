
import asyncio
import os
from server import generate_audio, generate_avatar_video

async def make_intro():
    print("Generating Sarah's Intro Audio...")
    text = "Hello, I am Sarah, your Senior Consultant. Click the chevron to speak with me directly!"
    
    b64, audio_path = await generate_audio(text)
    
    if audio_path:
        print(f"Audio generated at: {audio_path}")
        print("Generating Video (SadTalker)... this may take a minute...")
        
        video_path = generate_avatar_video(audio_path)
        
        if video_path:
            print(f"Video generated at: {video_path}")
            # Move to static/videos/intro_sarah.mp4
            final_path = "static/videos/intro_sarah.mp4"
            if os.path.exists(final_path):
                os.remove(final_path)
            
            # Since video_path is relative to where server runs, let's just copy
            import shutil
            shutil.copy(video_path, final_path)
            print("Intro video updated successfully! (Sarah)")
        else:
            print("Video generation failed.")
    else:
        print("Audio generation failed.")

if __name__ == "__main__":
    asyncio.run(make_intro())
