
import requests
import json
import time

URL = "http://localhost:8000/chat"
PAYLOAD = {
    "message": "Hello, can you explain the lymphatic system?",
    "session_id": "test_session_123"
}

def test_chat():
    print("Sending request to /chat...")
    try:
        # Use 'data' for Form-UrlEncoded or Multipart
        response = requests.post(URL, data=PAYLOAD, stream=True)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("Response Stream:")
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        data = json.loads(decoded[6:])
                        if data.get("type") == "text":
                            print(f"[TEXT]: {data.get('content')}")
                        elif data.get("type") == "audio":
                            print(f"[AUDIO]: {data.get('url')} (Duration: {data.get('duration')})")
                        elif data.get("type") == "video":
                            print(f"[VIDEO]: {data.get('url')}")
        else:
            print(f"Error: {response.text}")

    except Exception as e:
        print(f"Request Failed: {e}")

if __name__ == "__main__":
    time.sleep(5) # Wait for server start
    test_chat()
