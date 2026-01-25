import requests
import json
import time

URL = "http://localhost:8000/chat"

def chat(msg, user_id="debug_user_1", user_name="DebugUser", user_email="debug@test.com"):
    print(f"\nUser: {msg}")
    try:
        response = requests.post(URL, data={
            "message": msg,
            "user_name": user_name,
            "user_email": user_email
        }, stream=True)
        
        full_text = ""
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    if data['type'] == 'text':
                        print(f"Server (Text Chunk): {data['content']}", end="", flush=True)
                        full_text += data['content']
                    elif data['type'] == 'video':
                         print(f"\n[VIDEO QUEUED: {data['url']}]")
                except:
                    pass
        print("\n\nFull Response:", full_text)
        return full_text
    except Exception as e:
        print(f"Error: {e}")
        return ""

if __name__ == "__main__":
    t1 = chat("Hi there.")
    time.sleep(2)
    t2 = chat("My legs are swollen.")
    time.sleep(2)
    t3 = chat("What products do you have?")
    
    print("\n\n--- SUMMARY ---")
    if "Sarah" in t2 and "Sarah" in t3:
        print("FAIL: Repetitive Introduction Detected.")
    else:
        print("PASS: No excessive repetition.")
