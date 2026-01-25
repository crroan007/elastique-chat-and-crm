import requests
import uuid
import sqlite3
import time

BASE_URL = "http://localhost:8000"

def run_test_scenario(name, steps):
    session_id = str(uuid.uuid4())
    print(f"\n=== SCENARIO: {name} ===")
    print(f"Session: {session_id}")
    
    # Initialize Session
    requests.post(f"{BASE_URL}/chat", json={"message": "Event: Start", "session_id": session_id})
    
    for i, step in enumerate(steps):
        user_input = step['input']
        expected_fragment = step['expected']
        
        print(f"Step {i+1} | User: {user_input}")
        response = requests.post(f"{BASE_URL}/chat", json={
            "message": user_input,
            "session_id": session_id
        }).json()["response"]
        
        if any(f in response.lower() for f in expected_fragment):
            print(f"Step {i+1} | Bot: [SUCCESS] '{expected_fragment[0]}...' found.")
        else:
            print(f"Step {i+1} | Bot: [FAILURE] Expected one of {expected_fragment}")
            print(f"Actual Response: {response}")
            return False, session_id
            
    return True, session_id

def verify_db_persistence(email):
    conn = sqlite3.connect('data/elastique.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def main():
    # 1. TEST: Perfect Path (Identity -> Diagnosis -> Protocol)
    path_success, sid1 = run_test_scenario("The Perfect Path", [
        {"input": "Jim", "expected": ["nice to meet you", "email"]},
        {"input": "jim.test@elastique.com", "expected": ["thanks", "brings you here"]},
        {"input": "my ankles are swollen", "expected": ["legs", "mechanics", "routine", "leggings"]}
    ])

    # 2. TEST: Soft Pivot (Interruption)
    pivot_success, sid2 = run_test_scenario("The Soft Pivot", [
        {"input": "I want leggings", "expected": ["love to help", "name and email"]},
        {"input": "Sarah jim@pivot.com", "expected": ["thanks", "brings you here"]},
        {"input": "post-op recovery", "expected": ["surgery", "goal", "routine"]}
    ])

    # 3. TEST: Generic Greeting
    greet_success, sid3 = run_test_scenario("Generic Greeting", [
        {"input": "hi", "expected": ["sarah", "what's going on"]},
        {"input": "swollen legs", "expected": ["email", "name"]}
    ])

    print("\n" + "="*40)
    print("FINAL TEST REPORT")
    print("="*40)
    print(f"1. Perfect Path:  {'PASSED' if path_success else 'FAILED'}")
    print(f"2. Soft Pivot:    {'PASSED' if pivot_success else 'FAILED'}")
    print(f"3. Greeting:      {'PASSED' if greet_success else 'FAILED'}")
    
    # Verification DB
    db_ok = verify_db_persistence("jim.test@elastique.com")
    print(f"4. CRM Sync:      {'PASSED' if db_ok else 'FAILED'}")

if __name__ == "__main__":
    main()
