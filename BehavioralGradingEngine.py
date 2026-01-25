import requests
import uuid
import json
import os
from datetime import datetime

BASE_URL = "http://localhost:8000"
LOG_DIR = "data/stress_tests"

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

class BehavioralGradingEngine:
    def __init__(self):
        self.results = []

    def simulate_persona(self, persona_name, steps):
        print(f"\n>>> SIMULATING PERSONA: {persona_name}")
        session_id = f"test_{persona_name.lower().replace(' ', '_')}_{int(datetime.now().timestamp())}"
        transcript = []
        
        # Start
        requests.post(f"{BASE_URL}/chat", json={"message": "Event: Start", "session_id": session_id})

        for i, step in enumerate(steps):
            user_input = step['input']
            print(f"  Step {i+1} | User: {user_input}")
            
            response = requests.post(f"{BASE_URL}/chat", json={
                "message": user_input, "session_id": session_id
            }).json()["response"]
            
            # Auto-Grading Logic (Simplified)
            grade = self._grade_response(i, response, step.get('persona_type', 'neutral'))
            
            transcript.append({
                "step": i + 1,
                "user": user_input,
                "bot": response,
                "grade": grade
            })

        # Save Result
        report = {
            "persona": persona_name,
            "session_id": session_id,
            "transcript": transcript,
            "overall_score": sum(g['grade']['score'] for g in transcript) / len(transcript)
        }
        self.results.append(report)
        
        with open(f"{LOG_DIR}/{session_id}.json", "w") as f:
            json.dump(report, f, indent=2)

    def _grade_response(self, index, text, persona):
        score = 0
        reasons = []
        
        # 1. Empathy Check
        empathy_words = ["hear you", "understand", "acknowledging", "i know", "must be", "exciting", "great", "prioritizing"]
        if any(w in text.lower() for w in empathy_words):
            score += 2
            reasons.append("+Empathy Detected")
        
        # 2. Flow/Gate Check
        if "email" in text.lower() or "first name" in text.lower():
            score += 2
            reasons.append("+Identity Gate Pushed")
        
        # 3. Science Check
        if "http" in text.lower() or "evidence" in text.lower():
            score += 2
            reasons.append("+Science Reference Found")
            
        # 4. Product Tool
        if "product" in text.lower() or "supportive tool" in text.lower():
            score += 2
            reasons.append("+Product Soft-Sell Found")
            
        # 5. Length/Nuance
        if len(text.split()) > 30:
            score += 2
            reasons.append("+Depth of Education")

        return {"score": score, "reasons": reasons}

    def generate_audit_report(self):
        with open(f"{LOG_DIR}/final_audit.json", "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\nSimulation Complete. Results saved to {LOG_DIR}/final_audit.json")

def main():
    engine = BehavioralGradingEngine()

    # 1. PERSONA: Wandering Will (The Rambler)
    # Test: Extraction of single valid fact from noise.
    engine.simulate_persona("Wandering Will", [
        {"input": "Hi there. I was just telling my dog Buster about this. He's a golden retriever, loves the park.", "persona_type": "chaos"},
        {"input": "Will. will@ramble.com. Anyway, Buster chased a squirrel today. But yeah, my knee has been huge since the surgery.", "persona_type": "chaos"},
        {"input": "Oh, and my aunt had surgery too. She lives in Florida. Is it hot there? But yes, I need to fix this swelling.", "persona_type": "chaos"}
    ])

    # 2. PERSONA: Chaotic Cathy (The Topic Jumper)
    # Test: Context maintenance despite rapid topic switching.
    engine.simulate_persona("Chaotic Cathy", [
        {"input": "Do you sell face cream?", "persona_type": "chaos"},
        {"input": "Cathy. cathy@chaos.com. Actually, wait, are you a robot?", "persona_type": "chaos"},
        {"input": "My legs are so heavy at night. But I also need a new moisturizer.", "persona_type": "chaos"},
        {"input": "Focus on the legs though.", "persona_type": "chaos"}
    ])

    # 3. PERSONA: Verbose Valerie (The Over-Sharer)
    # Test: Handling massive text blocks without crashing or hallucinating.
    engine.simulate_persona("Verbose Valerie", [
        {"input": "Hello. I have a very complicated history. It started in 1998 with a sprained ankle...", "persona_type": "verbose"},
        {"input": "Valerie. val@verbose.com. Then in 2005 I had a C-section. Then in 2012 I broke my wrist. Now, specifically, I had liposuction on my thighs last week and the swelling is not going away. I've tried ice, heat, elevation, and prayer.", "persona_type": "verbose"},
        {"input": "I just want to know if I should be walking or resting because my doctor said one thing but the internet says another.", "persona_type": "verbose"}
    ])

    # 4. PERSONA: Athletic Annie (Performance Mode)
    # Test: Motivational Empathy instead of Restorative Sympathy.
    engine.simulate_persona("Athletic Annie", [
        {"input": "I'm training for a 5K and want to prevent ankle swelling.", "persona_type": "performance"},
        {"input": "Annie. annie@run.com. Just want to keep my legs fresh.", "persona_type": "performance"}
    ])

    # 5. PERSONA: Crisis Chris (Emergency)
    engine.simulate_persona("Crisis Chris", [
        {"input": "Chris. chris@danger.com. I think I'm having a heart attack.", "persona_type": "emergency"},
        {"input": "But my arm is numb too.", "persona_type": "emergency"}
    ])

    engine.generate_audit_report()

if __name__ == "__main__":
    main()
