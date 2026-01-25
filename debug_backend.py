import requests
import os

BASE_URL = "http://localhost:8000"

def test_avatar():
    url = f"{BASE_URL}/static/sarah_avatar.jpg"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            print(f"[PASS] Avatar found at {url}")
            return True
        else:
            print(f"[FAIL] Avatar 404 at {url}")
            return False
    except Exception as e:
        print(f"[FAIL] Server not reachable: {e}")
        return False

def test_chat():
    url = f"{BASE_URL}/chat"
    data = {"message": "Hello", "user_name": "TestUser", "user_email": "test@test.com"}
    try:
        r = requests.post(url, data=data)
        if r.status_code == 200:
            resp = r.json()
            reply = resp.get("reply", "")
            print(f"[PASS] Chat responding. Reply start: {reply[:50]}...")
            if "Sarah" in reply or "I am Sarah" in reply:
                 print("[PASS] Persona is Sarah.")
            return True
        else:
            print(f"[FAIL] Chat Status: {r.status_code} | {r.text}")
            return False
    except Exception as e:
        print(f"[FAIL] Chat Request Error: {e}")
        return False

if __name__ == "__main__":
    if test_avatar() and test_chat():
        print("\n[SUCCESS] Backend is fully operational.")
    else:
        print("\n[FAILURE] Backend issues detected.")
