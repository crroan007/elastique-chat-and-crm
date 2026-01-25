import requests
import json
import uuid

BASE_URL = "http://localhost:8000"
SESSION_ID = str(uuid.uuid4())

def test_protocol():
    print(f"Testing Session: {SESSION_ID}")
    
    # --- TEST 1: Identity Flow (Name -> Email) ---
    print("\n--- TEST 1: Name-Only Input ---")
    
    # 1. Start Session (State: identity_capture)
    requests.post(f"{BASE_URL}/chat", json={"message": "Event: Start", "session_id": SESSION_ID})
    
    # 2. Send Name
    resp_name = requests.post(f"{BASE_URL}/chat", json={
        "message": "Jim Johnson", 
        "session_id": SESSION_ID
    }).json()["response"]
    print(f"Bot (Name): {resp_name}")
    
    if "Nice to meet you" in resp_name:
        print("SUCCESS: Bot accepted name.")
    else:
        print("FAILURE: Bot rejected name or fell through.")

    # 3. Send Email
    resp_email = requests.post(f"{BASE_URL}/chat", json={
        "message": "jim@verify.com", 
        "session_id": SESSION_ID
    }).json()["response"]
    print(f"Bot (Email): {resp_email}")
    
    if "Thanks" in resp_email:
        print("SUCCESS: Bot accepted email.")
    else:
        print("FAILURE: Bot rejected email.")

    # --- TEST 2: Diagnosis Logic (Protocol) ---
    print("\n--- TEST 2: Specific Symptom 'Swollen ankles' ---")
    resp_symptom = requests.post(f"{BASE_URL}/chat", json={
        "message": "My ankles are swollen", 
        "session_id": SESSION_ID
    }).json()["response"]
    
    print(f"Bot: {resp_symptom[:100]}...") 
    
    # --- TEST 3: Soft Pivot (Interruption during Identity) ---
    print("\n--- TEST 3: Soft Pivot 'I want leggings' ---")
    
    # Reset Session for clean test
    NEW_SESSION = str(uuid.uuid4())
    requests.post(f"{BASE_URL}/chat", json={"message": "Event: Start", "session_id": NEW_SESSION})
    
    resp_pivot = requests.post(f"{BASE_URL}/chat", json={
        "message": "I want those leggings", 
        "session_id": NEW_SESSION
    }).json()["response"]
    print(f"Bot (Pivot): {resp_pivot}")
    
    if "First Name and Email Address" in resp_pivot:
        print("SUCCESS: Bot pivoted correctly.")
    else:
        print("FAILURE: Bot did not enforce identity gate.")

if __name__ == "__main__":
    test_protocol()
