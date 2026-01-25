
import requests
import time
import os

# We need a publicly accessible audio file for the mock
# We'll use a sample MP3 from a public source or a local dummy
SAMPLE_AUDIO_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3" # Short check

def test_transcription_handler():
    print("--- TESTING TRANSCRIPTION ---")
    
    payload = {
        "CallSid": "TC_DEBUG_123",
        "RecordingUrl": SAMPLE_AUDIO_URL 
    }
    
    try:
        url = "http://127.0.0.1:8000/voice/transcribe"
        print(f"POST {url}...")
        resp = requests.post(url, data=payload)
        
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        if resp.status_code == 200:
            print("[PASS] Webhook accepted recording.")
    except Exception as e:
        print(f"[FAIL] {e}")

if __name__ == "__main__":
    test_transcription_handler()
