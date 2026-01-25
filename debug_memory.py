
import requests
import uuid

BASE_URL = "http://127.0.0.1:8000/chat"

def test_memory_no_intent():
    print(f"\n=== Memory Test (No Intent) ===")
    session_id = f"mem_no_intent_{uuid.uuid4().hex[:8]}"
    
    # User with Name but No Intent (from previous runs)
    email = "bugfix@test.com" 
    
    payload = {
        "session_id": session_id,
        "message": "Event: Start",
        "email": email
    }
    
    resp = requests.post(BASE_URL, json=payload)
    text = resp.json().get("response", "")
    print(f"Bot Response: {text}")

    if "Friend" in text:
        print("[FAIL] 'Friend' greeting detected!")
    elif "BugFixUser" in text:
        # Check for expected variations
        if "continue discussing" in text:
             print("[PASS] Correctly identified Pending Protocol.")
        elif "working on your" in text:
             print("[FAIL] Treated Pending as Active.")
        elif "haven't set up a full protocol" in text:
             print("[WARN] Treated as No Protocol (Did query fail to find intent?).")
        else:
            print(f"[WARN] Greeting ok, but phrasing unexpected: {text}")
    else:
        print("[FAIL] Name 'BugFixUser' not recalled.")

if __name__ == "__main__":
    test_memory_no_intent()
