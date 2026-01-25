import requests
import uuid
import time
import random
import sys

BASE_URL = "http://127.0.0.1:8000"
ITERATIONS = 50

# Test Data
NAMES = ["Alice", "Bob", "Charlie", "Diana", "Evan", "Fiona", "George", "Hannah", "Ivan", "Julia"]
SYMPTOMS = ["swollen legs", "puffy ankles", "heavy calves", "post-op knee", "lipo recovery"]

class RegressionTester:
    def __init__(self):
        self.stats = {
            "fresh": {"pass": 0, "fail": 0},
            "active_resume": {"pass": 0, "fail": 0},
            "smart_return": {"pass": 0, "fail": 0}
        }
        self.session = requests.Session() # Reuse connections
    
    def _chat(self, session_id, message, email=None):
        payload = {"message": message, "session_id": session_id}
        if email: payload["email"] = email
        try:
            resp = self.session.post(f"{BASE_URL}/chat", json=payload, timeout=10)
            if resp.status_code == 200:
                time.sleep(1.0) # Very generous throttling
                return resp.json().get("response", "")
            return f"ERROR: {resp.status_code}"
        except Exception as e:
            return f"ERROR: {e}"

    def run_scenario_fresh(self, i):
        """
        Scenario A: Fresh User
        1. Start (Fresh ID) -> Expect Generic Greeting
        2. Identity -> Protocol
        """
        session_id = f"test_fresh_{uuid.uuid4()}"
        
        # Turn 1: Start
        resp_1 = self._chat(session_id, "Event: Start")
        if "Hello! I'm **Sarah**" not in resp_1:
            print(f"[Fresh #{i}] FAIL: Greeting mismatch. Got: {resp_1[:30]}...")
            self.stats["fresh"]["fail"] += 1
            return

        # Turn 2: Identity
        name = random.choice(NAMES)
        email = f"{name.lower()}_{uuid.uuid4().hex[:4]}@test.com"
        resp_2 = self._chat(session_id, f"My name is {name}, email {email}")
        
        # Turn 3: Symptom
        symptom = random.choice(SYMPTOMS)
        resp_3 = self._chat(session_id, f"I have {symptom}")
        
        # Turn 4: Agreement (Full Conversation)
        resp_4 = self._chat(session_id, "Yes, that sounds manageable")

        if "Saved" in resp_2 or "profile" in resp_2:
             self.stats["fresh"]["pass"] += 1
        else:
             print(f"[Fresh #{i}] FAIL: Flow broken at Turn 2. Got: {resp_2[:30]}...")
             self.stats["fresh"]["fail"] += 1

    def run_scenario_active_resume(self, i):
        """
        Scenario B: Active Resume
        1. Establish Session
        2. Refresh (Same ID) -> Expect 'Welcome back [Name]'
        """
        session_id = f"test_active_{uuid.uuid4()}"
        name = random.choice(NAMES)
        email = f"{name.lower()}_{uuid.uuid4().hex[:4]}@test.com"
        symptom = "swollen legs"

        # 1. Establish State
        self._chat(session_id, "Event: Start")
        self._chat(session_id, f"My name is {name}, email {email}")
        self._chat(session_id, f"I have {symptom}") # Sets diagnosis state

        # 2. Simulate Refresh (Same ID, "Event: Start")
        resp_refresh = self._chat(session_id, "Event: Start")
        
        if f"Welcome back, {name}" in resp_refresh and "legs" in resp_refresh.lower():
            self.stats["active_resume"]["pass"] += 1
        else:
            print(f"[Active #{i}] FAIL: Expected 'Welcome back {name}... legs'. Got: {resp_refresh[:50]}...")
            self.stats["active_resume"]["fail"] += 1

    def run_scenario_smart_return(self, i):
        """
        Scenario C: Smart Context Return
        1. Establish Session A (Save to CRM)
        2. Reset (New ID) + Known Email -> Expect 'Welcome back... last time [Topic]'
        """
        # Session A
        session_a = f"test_smart_a_{uuid.uuid4()}"
        name = random.choice(NAMES)
        email = f"{name.lower()}_{uuid.uuid4().hex[:4]}@test.com"
        symptom = "swollen legs" # Maps to 'legs' intent

        # 1. Establish State (and Trigger CRM Save)
        self._chat(session_a, "Event: Start")
        self._chat(session_a, f"My name is {name}, email {email}")
        self._chat(session_a, f"I have {symptom}") # This triggers crm.log_conversation_start

        # 2. Simulate Return (Session B, New ID, pass Email)
        session_b = f"test_smart_b_{uuid.uuid4()}"
        
        # Send Start WITH email (simulating frontend persistence)
        resp_return = self._chat(session_b, "Event: Start", email=email)
        
        # Expectation: "Welcome back [Name]! Last time we were looking at **legs**..."
        if f"Welcome back {name}" in resp_return and "legs" in resp_return.lower():
            self.stats["smart_return"]["pass"] += 1
        else:
            print(f"[Smart #{i}] FAIL: Expected 'Welcome back {name}... legs'. Got: {resp_return[:100]}...")
            self.stats["smart_return"]["fail"] += 1

    def run(self):
        print(f"--- Starting Regression Suite ({ITERATIONS} iterations per scenario) ---")
        
        print("\n[Scenario A] Fresh User...")
        for i in range(ITERATIONS):
            self.run_scenario_fresh(i)
            if i % 10 == 0: print(f".", end="", flush=True)
            
        print("\n\n[Scenario B] Active Resume...")
        for i in range(ITERATIONS):
            self.run_scenario_active_resume(i)
            if i % 10 == 0: print(f".", end="", flush=True)

        print("\n\n[Scenario C] Smart Return (CRM)...")
        for i in range(ITERATIONS):
            self.run_scenario_smart_return(i)
            if i % 10 == 0: print(f".", end="", flush=True)

        print("\n\n--- REPORT CARD ---")
        print(f"Fresh Users:    {self.stats['fresh']['pass']}/{ITERATIONS} Pass")
        print(f"Active Resume:  {self.stats['active_resume']['pass']}/{ITERATIONS} Pass")
        print(f"Smart Return:   {self.stats['smart_return']['pass']}/{ITERATIONS} Pass")
        
        total_pass = sum(s['pass'] for s in self.stats.values())
        total_runs = ITERATIONS * 3
        print(f"TOTAL SCORE:    {total_pass}/{total_runs} ({(total_pass/total_runs)*100:.1f}%)")

if __name__ == "__main__":
    tester = RegressionTester()
    tester.run()
