
import json
import uuid
import sys
import os

# Ensure we can import services
sys.path.append(os.getcwd())

from services.crm_service import CRMService

def test_marketing_hub():
    crm = CRMService()
    print("--- TESTING MARKETING HUB SEGMENTATION ---")
    
    # 1. Create Dummy Contacts for Testing
    print("1. Creating Test Contacts...")
    # High Value Customer
    cid1 = crm.create_or_update_contact("whale@test.com", "Whale", "User")
    conn = crm._get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE contacts SET engagement_score = 90, lifecycle_stage = 'customer', lifetime_value = 500 WHERE id = ?", (cid1,))
    
    # Low Value Lead
    cid2 = crm.create_or_update_contact("minnow@test.com", "Minnow", "User")
    cursor.execute("UPDATE contacts SET engagement_score = 20, lifecycle_stage = 'lead', lifetime_value = 0 WHERE id = ?", (cid2,))
    conn.commit()
    conn.close()
    
    # 2. Create Segment Criteria
    segment_id = str(uuid.uuid4())
    criteria = {
        "and": [
            {"lifecycle_stage": "customer"},
            {"engagement_score": {">": 50}}
        ]
    }
    
    conn = crm._get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO segments (id, name, criteria, last_count) VALUES (?, 'High Value Customers', ?, 0)",
                   (segment_id, json.dumps(criteria)))
    conn.commit()
    conn.close()
    
    print(f"2. Created Segment '{segment_id}' with criteria: {criteria}")
    
    # 3. Evaluate Segment
    print("3. Running Evaluation...")
    matches = crm.evaluate_segment(segment_id)
    
    print(f"4. Result: Found {len(matches)} matches.")
    
    # 4. Verification
    found_emails = [m['email'] for m in matches]
    if "whale@test.com" in found_emails and "minnow@test.com" not in found_emails:
        print("[PASS] Segmentation Logic Verified!")
    else:
        print(f"[FAIL] Unexpected matches: {found_emails}")

if __name__ == "__main__":
    test_marketing_hub()
