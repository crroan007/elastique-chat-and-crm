import requests
import json
import sys
import time

URL = "http://localhost:8000/chat"

TEST_CASES = [
    {
        "name": "General Greeting",
        "input": "Hello, who are you?",
        "expected_keywords": ["Elastique", "assistant", "help"]
    },
    {
        "name": "Product specific (Leggings)",
        "input": "I need some leggings for travel",
        "expected_keywords": ["legging", "travel", "L'Original", "Fierce", "Lisse"]
    },
    {
        "name": "Symptom/Benefit (Lymphatic)",
        "input": "I have swelling in my legs.",
        "expected_keywords": ["swelling", "lymphatic", "circulation", "MicroPerle"]
    },
    {
        "name": "Out of Scope",
        "input": "What is the capital of France?",
        "expected_keywords": ["Elastique", "limit", "sorry", "assist with", "products"] 
        # Note: 'goal_prompt_fallback.txt' likely instructs it to stay on topic or handle it gracefully. 
        # We check if it steers back or answers generic. 
        # If the old bot answered everything, we might need to adjust expectation.
    }
]

def run_tests():
    print(f"--- Starting Logic Verification on {URL} ---")
    results = []
    
    # Check Server Health
    try:
        requests.get("http://localhost:8000/health")
    except:
        print("CRITICAL: Server is not running. Start server.py first.")
        sys.exit(1)

    for test in TEST_CASES:
        print(f"\nRunning Test: {test['name']}...")
        payload = {"message": test['input']}
        
        try:
            start_time = time.time()
            res = requests.post(URL, json=payload)
            duration = time.time() - start_time
            
            if res.status_code == 200:
                data = res.json()
                reply = data.get("reply", "")
                card = data.get("product_card", "")
                
                # Verification Logic
                passed = True
                missing_keywords = []
                
                # Check for at least ONE expected keyword match if list provided
                if test['expected_keywords']:
                    found = False
                    for kw in test['expected_keywords']:
                        if kw.lower() in reply.lower():
                            found = True
                            break
                    if not found:
                        passed = False
                        missing_keywords = test['expected_keywords']

                # Output Result
                status = "PASS" if passed else "FAIL"
                print(f"  Status: {status} ({duration:.2f}s)")
                print(f"  Reply: {reply[:100]}...")
                if card:
                    print(f"  [+] Product Card Returned")
                
                results.append({
                    "test": test['name'],
                    "status": status,
                    "reply_snippet": reply[:200],
                    "card_present": bool(card),
                    "duration": duration
                })
                
            else:
                print(f"  ERROR: HTTP {res.status_code}")
                
        except Exception as e:
            print(f"  ERROR: {str(e)}")
            
    # Generate Report
    print("\n\n--- SUMMARY ---")
    for r in results:
        print(f"{r['status']}: {r['test']}")

if __name__ == "__main__":
    run_tests()
