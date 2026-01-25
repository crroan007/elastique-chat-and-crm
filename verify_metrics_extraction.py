import requests
import sqlite3
import uuid
import json
import time

BASE_URL = "http://localhost:8000"
DB_PATH = "data/elastique.db"

def verify_metrics():
    print("--- Verifying Agentic Metrics Extraction ---")
    
    # 1. Seed Data directly into DB (bypassing chat flow to ensure specific content)
    session_id = f"test_metrics_{int(time.time())}"
    conversation_id = str(uuid.uuid4())
    contact_id = str(uuid.uuid4())
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create Contact
    cursor.execute("INSERT INTO contacts (id, email) VALUES (?, ?)", (contact_id, f"{session_id}@test.com"))
    
    # Create Conversation
    cursor.execute("INSERT INTO conversations (id, contact_id, session_id) VALUES (?, ?, ?)", 
                   (conversation_id, contact_id, session_id))
    
    # Create Transcript (The "Golden Path")
    messages = [
        ("user", "Hi, I have terrible swelling in my ankles after my lipo surgery."),
        ("bot", "I understand. For post-op recovery, I recommend our Lymphatic Drainage Protocol."),
        ("user", "That sounds exactly like what I need. I will start immediately."),
        ("bot", "Excellent. Would you like to schedule a follow-up consultation?"),
        ("user", "Yes, let's book it for next Friday."),
        ("bot", "Done. I have scheduled your appointment."),
    ]
    
    for sender, content in messages:
        cursor.execute("INSERT INTO messages (conversation_id, sender, content) VALUES (?, ?, ?)", 
                       (conversation_id, sender, content))
        
    print(f"1. Seeded Conversation {session_id} with {len(messages)} messages.")
    
    # [Verify seed]
    check = conn.execute("SELECT count(*) FROM messages WHERE conversation_id = ?", (conversation_id,)).fetchone()
    print(f"   [Pre-Check] DB has {check[0]} messages for this conversation.")
    
    conn.close()
    
    time.sleep(1.0) # Ensure SQLite write propagates
    
    # 2. Trigger Analysis Endpoint
    print(f"2. Calling /chat/end for session {session_id}...")
    try:
        resp = requests.post(f"{BASE_URL}/chat/end", json={"session_id": session_id, "message": "END_SESSION"})
        data = resp.json()
        print(f"   API Response: {json.dumps(data, indent=2)}")
        
        metrics = data.get("metrics", {})
        print(f"   [DEBUG] Metrics Type: {type(metrics)}")
        print(f"   [DEBUG] Metrics Content: {metrics}")
        
        if isinstance(metrics, str):
            print("   [DEBUG] Parsing metrics from string...")
            metrics = json.loads(metrics)

        # 3. Assertions
        print("\n3. Verifying Metrics...")
        
        # Check User Need
        if "swelling" in metrics.get("user_need", "").lower():
            print("   PASS: User Need captured.")
        else:
            print(f"   FAIL: User Need mismatch. Got: {metrics.get('user_need')}")

        # Check Alignment
        if metrics.get("alignment_met") is True:
             print("   PASS: Alignment (True) captured.")
        else:
             print(f"   FAIL: Alignment mismatch. Got: {metrics.get('alignment_met')}")
             
        # Check Appointment
        if metrics.get("appointment_scheduled") is True:
             print("   PASS: Appointment (True) captured.")
        else:
             print(f"   FAIL: Appointment mismatch. Got: {metrics.get('appointment_scheduled')}")

    except Exception as e:
        print(f"   FAIL: API Call Error: {e}")

if __name__ == "__main__":
    verify_metrics()
