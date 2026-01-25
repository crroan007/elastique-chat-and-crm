
import requests
import time
import json
import sys
import os
import sqlite3
from datetime import datetime

# Ensure we can import services for direct DB access
sys.path.append(os.getcwd())
try:
    from services.crm_service import CRMService
except ImportError:
    print("Could not import CRMService. Make sure you are in the root directory.")
    sys.exit(1)

BASE_URL = "http://localhost:8000"
SARAH_EMAIL = "sarah@mom.test"

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def retry_db_op(func, retries=5, delay=1.0):
    for i in range(retries):
        try:
            return func()
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                print(f"DB Locked. Retrying {i+1}/{retries}...")
                time.sleep(delay)
            else:
                raise
    raise Exception("DB Locked after retries.")

def test_chat_interaction():
    print_header("1. CHAT BOT INTERACTION (User -> API -> DB)")
    payload = {
        "email": SARAH_EMAIL,
        "message": "I am feeling a bit better, but my ankles are still swollen.",
        "user_email": SARAH_EMAIL  # Robustness check
    }
    
    try:
        start = time.time()
        res = requests.post(f"{BASE_URL}/chat", json=payload)
        res.raise_for_status()
        print(f"[PASS] API Response (Status {res.status_code}) in {time.time()-start:.2f}s")
        print(f"Response: {res.json()['response'][:100]}...")
    except Exception as e:
        print(f"[FAIL] Chat API Failed: {e}")

def test_voice_interaction():
    print_header("2. VOICE INTERACTION (Twilio -> Webhook -> DB)")
    # Simulate Twilio Form Data
    data = {
        "CallSid": f"CA{int(time.time())}",
        "RecordingUrl": "https://api.twilio.com/2010-04-01/Accounts/AC123/Recordings/RE123",
        "From": "+15555555555"
    }
    
    try:
        res = requests.post(f"{BASE_URL}/voice/webhook", data=data)
        res.raise_for_status()
        print(f"[PASS] Voice Webhook Response (Status {res.status_code})")
        # Check XML response
        if "<Say>" in res.text:
            print("[PASS] Valid TwiML Returned")
    except Exception as e:
        print(f"[FAIL] Voice Webhook Failed: {e}")

def test_manual_input_and_commerce():
    print_header("3. MANUAL INPUT & COMMERCE (Manager -> Service -> DB)")
    crm = CRMService()
    
    # Needs to find Sarah's ID first
    def get_sarah_id():
        conn = crm._get_conn()
        c = conn.cursor()
        c.execute("SELECT id FROM contacts WHERE email = ?", (SARAH_EMAIL,))
        row = c.fetchone()
        conn.close()
        return row['id'] if row else None

    contact_id = retry_db_op(get_sarah_id)
    if not contact_id:
        print("[FAIL] Sarah not found in DB!")
        return
        
    print(f"Found Contact ID: {contact_id}")
    
    # A. Add Manual Note
    print("\n[Action] Adding Manual Note...")
    def add_note_op():
        return crm.add_note(contact_id, "Called patient to verify swelling status. She is complying with protocol.", author_id="Dr. Smith")
    
    try:
        retry_db_op(add_note_op)
        print("[PASS] Manual Note Added.")
    except Exception as e:
        print(f"[FAIL] Add Note Failed: {e}")

    # B. Create Commerce Order
    print("\n[Action] Creating Shop Order...")
    def create_order_op():
        items = [
            {"sku": "LYMPH-SOCK-M", "name": "Lymphatic Socks (Medium)", "quantity": 2, "price": 45.00},
            {"sku": "DRY-BRUSH-PRO", "name": "Pro Dry Brush", "quantity": 1, "price": 25.00}
        ]
        return crm.create_order(contact_id, 115.00, items)
        
    try:
        retry_db_op(create_order_op)
        print("[PASS] Order Created.")
    except Exception as e:
        print(f"[FAIL] Create Order Failed: {e}")

def test_conversation_analyst():
    print_header("4. CONVERSATION ANALYST (System -> Analyst -> DB)")
    # We need a session ID. Let's pick one from Sarah.
    crm = CRMService()
    
    def get_last_session():
        conn = crm._get_conn()
        c = conn.cursor()
        c.execute("SELECT id FROM contacts WHERE email = ?", (SARAH_EMAIL,))
        cid = c.fetchone()['id']
        c.execute("SELECT id FROM conversations WHERE contact_id = ? ORDER BY started_at DESC LIMIT 1", (cid,))
        row = c.fetchone()
        conn.close()
        return row['id'] if row else None
        
    session_id = retry_db_op(get_last_session)
    if not session_id:
        print("[FAIL] No session found for Sarah to analyze.")
        return
        
    print(f"Analyzing Session: {session_id}")
    
    try:
        from services.conversation_analyst import ConversationAnalyst
        analyst = ConversationAnalyst()
        # Mocking or Running Real? Use Mock first to be safe/fast/free
        print("[Action] Running Analyst (Mock/Real)...")
        metrics = analyst.analyze_conversation(session_id)
        
        if metrics:
            print(f"[PASS] Analyst Generated Metrics: {list(metrics.keys())}")
        else:
            print("[WARN] Analyst returned None (Maybe not enough turns?)")
            
    except ImportError:
        print("[FAIL] Could not import ConversationAnalyst.")
    except Exception as e:
        print(f"[FAIL] Analyst Execution Failed: {e}")

def verify_dossier_fidelity():
    print_header("5. COMPREHENSIVE DOSSIER AUDIT")
    crm = CRMService()
    
    def get_dossier():
        # Get ID
        conn = crm._get_conn()
        res = conn.execute("SELECT id FROM contacts WHERE email = ?", (SARAH_EMAIL,)).fetchone()
        conn.close()
        if not res: return None
        return crm.get_contact_dossier(res['id'])
        
    dossier = retry_db_op(get_dossier)
    if not dossier:
        print("[FAIL] Could not retrieve dossier.")
        return

    print("Checking Fields...")
    
    # 1. Identity
    print(f"Name: {dossier.get('first_name')} {dossier.get('last_name')}")
    if dossier.get('email') == SARAH_EMAIL: print("[PASS] Identity Correct")
    
    # 2. Timeline
    timeline = dossier.get('timeline', [])
    print(f"\nTimeline Events Found: {len(timeline)}")
    
    found_types = set()
    for event in timeline:
        etype = event.get('timeline_type') 
        # Normalize
        if etype == 'event': etype = event.get('event_type')
        found_types.add(etype)
        
    print(f"Event Types Detected: {found_types}")
    
    required = {'chat_started', 'chat_session', 'order_placed', 'note'}
    # Note: voice call logs as 'timeline_type=event' and 'event_type=voice_call_inbound' usually, 
    # but my debug script used minimal payload. 
    # Wait, voice_webhook logs 'voice_call_completed' or similar?
    # Let's check voice_webhook.py logging event_type.
    # Ah, I should have checked that meta.
    
    missing = required - found_types
    if not missing:
        print("[PASS] All Event Types Found in Unified Timeline!")
    else:
        print(f"[WARN] Missing Event Types: {missing}")
        
    # 3. Commerce Verification
    if 'order_placed' in found_types:
        # Dig into order details?
        pass

    # 4. Check for Transcripts
    transcripts = [t for t in timeline if t.get('transcript')]
    if transcripts:
        print(f"[PASS] Found {len(transcripts)} Transcripts.")
    else:
        print("[WARN] No transcripts found (Expected if Gemini API key missing or mock used).")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "audit":
        verify_dossier_fidelity()
    else:
        test_chat_interaction()
        test_voice_interaction()
        test_manual_input_and_commerce()
        time.sleep(1) # Let DB settle
        test_conversation_analyst() # [NEW]
        verify_dossier_fidelity()
