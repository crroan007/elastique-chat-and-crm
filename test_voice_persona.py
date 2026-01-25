import requests
import base64

BASE_URL = "http://localhost:8000"

def test_voice_persona():
    print("=== TESTING SOFT AMERICAN VOICE REVERT ===")
    msg = "I understand how difficult this journey can be. I am here to support you every step of the way."
    
    try:
        resp = requests.post(f"{BASE_URL}/chat", json={"message": msg, "session_id": "test_persona"}).json()
        audio_data = resp.get("audio")
        
        if audio_data:
            print(f"SUCCESS: Audio received ({len(audio_data)} bytes). Saving to 'soft_sarah_test.mp3'.")
            with open("soft_sarah_test.mp3", "wb") as f:
                f.write(base64.b64decode(audio_data))
            print("Please open 'soft_sarah_test.mp3' and verify it sounds Soft, American, and Empathetic.")
        else:
            print("FAILURE: No audio.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_voice_persona()
