
import sqlite3
import sys
import os

# Add path to import services
sys.path.append(os.getcwd())
from services.crm_service import CRMService

def inspect_data(email):
    print(f"--- INSPECTING DATA FOR: {email} ---")
    
    # 1. Raw DB Check
    conn = sqlite3.connect('data/elastique.db')
    cursor = conn.cursor()
    
    # Check Contact
    cursor.execute("SELECT id, email, first_name FROM contacts WHERE email = ?", (email,))
    contact = cursor.fetchone()
    print(f"RAW CONTACT: {contact}")
    
    if contact:
        cid = contact[0]
        # Check Conversations
        cursor.execute("SELECT id, primary_intent, started_at FROM conversations WHERE contact_id = ?", (cid,))
        convs = cursor.fetchall()
        print(f"RAW CONVERSATIONS ({len(convs)}):")
        for c in convs:
            print(f" - {c}")

    conn.close()

    # 2. Service Logic Check
    crm = CRMService()
    try:
        last_active = crm.get_last_interaction(email)
        print(f"\nSERVICE RETURN (get_last_interaction): {last_active}")
    except Exception as e:
        print(f"SERVICE ERROR: {e}")

if __name__ == "__main__":
    # Check a few potential emails the user might be using
    inspect_data("bugfix@test.com")
    inspect_data("strict@test.com")
