from services.crm_service import CRMService
import uuid
import time

def debug_crm():
    print("--- Debugging CRM Logic ---")
    crm = CRMService("data/elastique.db")
    
    email = f"debug_{int(time.time())}@test.com"
    session_id = f"sess_{int(time.time())}"
    
    print(f"1. logging conversation for {email} (intent='legs')...")
    crm.log_conversation_start(session_id, email, intent="legs")
    
    print("2. Retrieving last interaction...")
    last = crm.get_last_interaction(email)
    print(f"   Result: {last}")
    
    if last and last["intent"] == "legs":
        print("PASS: CRM Logic is solid.")
    else:
        print("FAIL: CRM Logic broken.")

if __name__ == "__main__":
    debug_crm()
