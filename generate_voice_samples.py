import asyncio
import edge_tts

# The 5 Candidates
VOICES = {
    "Aria (Professional)": "en-US-AriaNeural",
    "Jenny (Friendly)": "en-US-JennyNeural",
    "Michelle (Warm)": "en-US-MichelleNeural",
    "Sonia (British/Precise)": "en-GB-SoniaNeural",
    "Ava (Modern)": "en-US-AvaNeural"
}

# Phonetic Test Sentence
TEXT = "The quick brown fox jumps over the lazy dog. She sells seashells by the seashore. Sphinx of black quartz, judge my vow."

async def generate_samples():
    print(f"Generating samples for: {TEXT}")
    
    html_content = """
    <html>
    <head>
        <title>Sarah Voice Auditions</title>
        <style>
            body { font-family: sans-serif; padding: 40px; background: #f5f5f5; }
            .card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h2 { margin-top: 0; color: #6C5CE7; }
            p { color: #666; font-style: italic; }
            audio { width: 100%; margin-top: 10px; }
        </style>
    </head>
    <body>
    <h1>Voice Audition: Sarah</h1>
    <p>Test Sentence: "The quick brown fox jumps over the lazy dog. She sells seashells by the seashore..."</p>
    """

    for name, voice_id in VOICES.items():
        filename = f"sample_{voice_id.replace('-', '_')}.mp3"
        print(f"Generating {name} -> {filename}...")
        
        try:
            communicate = edge_tts.Communicate(TEXT, voice_id)
            await communicate.save(filename)
            
            html_content += f"""
            <div class="card">
                <h2>{name}</h2>
                <p>{voice_id}</p>
                <audio controls src="{filename}"></audio>
            </div>
            """
        except Exception as e:
            print(f"Error generating {name}: {e}")
            
    html_content += "</body></html>"
    
    with open("voice_test.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("Done! Open 'voice_test.html' to listen.")

if __name__ == "__main__":
    asyncio.run(generate_samples())
