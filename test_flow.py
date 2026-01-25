import requests
import json

BASE_URL = "http://localhost:8000"
SESSION_ID = "test_user_001"

def send_chat(msg, email=None):
    payload = {"message": msg, "session_id": SESSION_ID, "email": email}
    try:
        res = requests.post(f"{BASE_URL}/chat", json=payload)
        res.raise_for_status()
        return res.json()["response"]
    except Exception as e:
        return f"Error: {e}"

def test_flow():
    print(f"--- Starting Test Flow for Session: {SESSION_ID} ---\n")
    
    # 1. Start / Diagnosis
    print("User: I have swelling in my legs.")
    res = send_chat("I have swelling in my legs.", "test@example.com")
    print(f"Bot: {res}\n")
    
    # 2. Agree to Protocol
    print("User: Yes, that sounds manageable.")
    res = send_chat("Yes, that sounds manageable.")
    print(f"Bot: {res}\n")
    
    # Check if PDF link is in response (Simulated)
    # The bot script says "I'm generating..." but the actual generation happens via /generate-protocol usually triggered by FE.
    # However, for this text-bot flow, logic might just say it.
    
    # 3. Choose Clothing (Fork)
    print("User: I'd like to see clothing.")
    res = send_chat("I'd like to see clothing.")
    print(f"Bot: {res}\n")
    
    # 4. Refinement Loop Q1
    print("User: Sure, ask away.")
    res = send_chat("Sure, ask away.")
    print(f"Bot: {res}\n")
    
    # 5. Refinement Answer 1
    print("User: High compression, please.")
    res = send_chat("High compression, please.")
    print(f"Bot: {res}\n")
    
    print("--- Test Complete ---")

if __name__ == "__main__":
    test_flow()
