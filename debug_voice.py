
import requests
import xml.etree.ElementTree as ET

def test_voice_webhook():
    print("--- TESTING TWILIO VOICE WEBHOOK ---")
    url = "http://127.0.0.1:8000/voice/webhook"
    
    # Mock Twilio Payload
    payload = {
        "From": "+15551234567",
        "CallSid": "CA1234567890abcdef",
        "To": "+15559876543"
    }
    
    try:
        resp = requests.post(url, data=payload)
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            print("\nResponse XML:")
            print(resp.text)
            
            # Simple XML Validation
            root = ET.fromstring(resp.text)
            if root.tag == "Response":
                print("\n[PASS] Valid TwiML Response.")
                if root.find("Say") is not None:
                    print(f"[PASS] Contains <Say>: {root.find('Say').text}")
            else:
                print("[FAIL] Invalid TwiML Root.")
        else:
            print(f"[FAIL] Server Error: {resp.text}")
            
    except Exception as e:
        print(f"[FAIL] Connection Error: {e}")

if __name__ == "__main__":
    test_voice_webhook()
