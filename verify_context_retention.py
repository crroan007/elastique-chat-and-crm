import requests
import uuid
import time
import json

BASE_URL = "http://localhost:8000"

def verify_context_retention():
    print("--- Starting Verification: Smart Context Retention ---")
    
    # 1. New Identity
    email = f"user_{int(time.time())}@test.com"
    name = "Tester"
    session_a = f"session_{int(time.time())}"
    
    print(f"1. Creating Profile for {email}...")
    
    # Send Identity + Diagnosis
    msg_1 = f"My name is {name}, email {email}, and my legs are swollen."
    resp_1 = requests.post(f"{BASE_URL}/chat", json={"message": msg_1, "session_id": session_a, "email": email})
    data_1 = resp_1.json()
    
    # Check if backend identified us
    if data_1.get("user_email") == email:
        print("   PASS: Backend returned user_email in response.")
    else:
        print("   FAIL: Backend did not return identity metadata.")
    
    # [DEBUG] Check DB directly
    try:
        import sqlite3
        conn = sqlite3.connect("data/elastique.db")
        cursor = conn.cursor()
        cursor.execute("SELECT primary_intent FROM conversations WHERE id = ?", (session_a,))
        row = cursor.fetchone()
        print(f"   [DEBUG DB] Session A Intent: {row[0] if row else 'NOT FOUND'}")
        conn.close()
    except Exception as e:
        print(f"   [DEBUG DB] Error: {e}")

    print(f"   Bot: {data_1['response'][:50]}...")
    
    # 2. Simulate "Session Reset" (New Session ID, but known email)
    session_b = f"session_{int(time.time())+100}" # New ID
    
    print(f"2. Simulating Return (New Session ID {session_b})...")
    # Sending 'Event: Start' with known email
    resp_2 = requests.post(f"{BASE_URL}/chat", json={
        "message": "Event: Start", 
        "session_id": session_b,
        "email": email 
    })
    
    response_text = resp_2.json().get('response', '')
    print(f"   Bot: {response_text}")
    
    # 3. Verification
    if "Welcome back" in response_text and "Tester" in response_text:
        if "swollen" in response_text.lower() or "legs" in response_text.lower():
            print("PASS: Smart Retention worked! (Recognized Name + Topic)")
        else:
            print("PARTIAL PASS: Recognized Name but missed Topic.")
    else:
        print("FAIL: Smart Retention failed. Treated as stranger.")

if __name__ == "__main__":
    verify_context_retention()
