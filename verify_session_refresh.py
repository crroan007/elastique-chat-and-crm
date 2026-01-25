import requests
import uuid
import time

BASE_URL = "http://localhost:8000"

def verify_session_persistence():
    print("--- Starting Verification: Session Persistence & Reset ---")
    
    # 1. Start Session A
    session_a = f"session_{int(time.time())}"
    print(f"1. Starting Session A ({session_a})...")
    resp_a = requests.post(f"{BASE_URL}/chat", json={"message": "Event: Start", "session_id": session_a})
    print(f"   Response: {resp_a.json().get('response', '')[:50]}...")
    
    # 2. Chat in Session A (Establish State)
    print("2. Establishing State (My name is Bob)...")
    requests.post(f"{BASE_URL}/chat", json={"message": "My name is Bob", "session_id": session_a, "user_email": "bob@test.com"})
    
    # 3. Simulate "Refresh" (Same Session ID)
    print("3. Simulating Page Refresh (Same Session ID)...")
    resp_refresh = requests.post(f"{BASE_URL}/chat", json={"message": "Event: Start", "session_id": session_a})
    result_refresh = resp_refresh.json().get('response', '')
    print(f"   Response: {result_refresh[:50]}...")
    
    if "Welcome back" in result_refresh or "Bob" in result_refresh:
        print("PASS: Backend correctly identifies returning session.")
    else:
        print("FAIL: Backend treated returning session as new.")

    # 4. Simulate "Reset" (New Session ID)
    session_b = f"session_{int(time.time())+100}"
    print(f"4. Simulating 'Reset Chat' (New Session ID {session_b})...")
    resp_reset = requests.post(f"{BASE_URL}/chat", json={"message": "Event: Start", "session_id": session_b})
    result_reset = resp_reset.json().get('response', '')
    print(f"   Response: {result_reset[:50]}...")
    
    if "Hello!" in result_reset and "Sarah" in result_reset and "Welcome back" not in result_reset:
        print("PASS: Backend treated Reset session as fresh.")
    else:
        print(f"FAIL: Backend did not give fresh greeting. Got: {result_reset[:50]}...")

if __name__ == "__main__":
    verify_session_persistence()
