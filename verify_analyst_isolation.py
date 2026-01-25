import sqlite3
import uuid
import time
import json
from services.conversation_analyst import ConversationAnalyst

DB_PATH = "data/elastique.db"

class MockMultimodal:
    """Mock Gemini for isolation test"""
    def __init__(self):
        self.model = None # Trigger SMART MOCK mode

def verify_isolation():
    print("--- Verifying Analyst Logic (Isolation) ---")
    
    # 1. Setup DB Data
    session_id = f"iso_{int(time.time())}"
    conversation_id = str(uuid.uuid4())
    contact_id = str(uuid.uuid4())
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO contacts (id, email) VALUES (?, ?)", (contact_id, f"{session_id}@test.com"))
    cursor.execute("INSERT INTO conversations (id, contact_id, session_id) VALUES (?, ?, ?)", 
                   (conversation_id, contact_id, session_id))
                   
    messages = [
        ("user", "I need to book an appointment regarding swelling."),
        ("bot", "Sure, lets do it."),
        ("user", "Great, Friday works."),
    ]
    
    for sender, content in messages:
        cursor.execute("INSERT INTO messages (conversation_id, sender, content) VALUES (?, ?, ?)", 
                       (conversation_id, sender, content))
                       
    conn.commit()
    conn.close()
    
    print(f"1. Seeded Session {session_id}")
    
    # 2. Run Analyst directly
    mm_service = MockMultimodal()
    analyst = ConversationAnalyst(mm_service, db_path=DB_PATH)
    
    print("2. Running analyze_session...")
    metrics = None
    try:
        # Since analyze_session is async, we need asyncio
        import asyncio
        metrics = asyncio.run(analyst.analyze_session(session_id))
        
        print(f"3. Result: {json.dumps(metrics, indent=2)}")
        
        if metrics and metrics.get("appointment_scheduled") is True:
            print("PASS: Logic works in isolation.")
        else:
            print("FAIL: Logic failed (None or missing appt).")
            
    except Exception as e:
        print(f"CRASH: {e}")

if __name__ == "__main__":
    verify_isolation()
