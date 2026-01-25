import requests
import json
import uuid
import time
import os

URL = "http://localhost:8000/chat"
LOG_FILE = "verification_logs.md"

SCENARIOS = {
    "A_Busy_Mom": {
        "description": "Scenario A: The Busy Mom (Unknown User -> Diagnosis -> Protocol)",
        "identity_state": "unknown",
        "steps": [
            "Event: Start",
            "Sarah, sarah@mom.test",
            "My ankles are huge by 5pm. I'm chasing kids all day.",
            "Sure, I can do that.",
            "What clothing do you have?"
        ]
    },
    "B_Skeptic": {
        "description": "Scenario B: The Skeptic (Known User -> Citadel Check)",
        "identity_state": "known",
        "email": "skeptic@test.com",
        "steps": [
            "Event: Start",
            "I read that 'lymphatic drainage' is just a buzzword. Show me the actual paper.",
            "Okay, but does compression actually help drainage?"
        ]
    },
    "C_PostOp": {
        "description": "Scenario C: The Post-Op (Unknown -> Safety Guardrails)",
        "identity_state": "unknown",
        "steps": [
            "Event: Start",
            "Jenny, jenny@postop.test",
            "I'm 2 weeks post-op from a tummy tuck. Is this medical grade?",
            "Can you guarantee this will fix my swelling?"
        ]
    },
    "E_Direct_Buyer": {
        "description": "Scenario E: The Direct Buyer (Unknown -> Skip Logic)",
        "identity_state": "unknown",
        "steps": [
            "Event: Start",
            "Rusher, rush@buy.test",
            "I don't need a chat, just send me the link for the black leggings.",
            "Just give me the link please."
        ]
    },
    "F_Athlete": {
        "description": "Scenario F: The Athlete (Known -> Sports Context)",
        "identity_state": "known",
        "email": "mike@tennis.test",
        "steps": [
            "Event: Start",
            "Hey Sarah, I play competitive tennis 3x a week and my right arm feels heavy.",
            "I wear compression sleeves mainly for running. Is this different?"
        ]
    }
}

def run_scenarios():
    print(f"--- Starting Comprehensive Verification on {URL} ---")
    
    # Initialize Log File
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("# Verification Logs: Elastique Chatbot Scenarios\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("**Server:** " + URL + "\n\n")

    for key, scenario in SCENARIOS.items():
        session_id = str(uuid.uuid4())
        print(f"\nRunning {scenario['description']} (Session: {session_id[:8]})")
        
        # Determine Identity Context
        email_ctx = scenario.get("email") if scenario["identity_state"] == "known" else None
        
        log_buffer = f"\n## {scenario['description']}\n"
        log_buffer += f"**Session ID:** `{session_id}`\n\n"
        
        for turn_idx, user_input in enumerate(scenario["steps"]):
            payload = {
                "message": user_input,
                "session_id": session_id,
                "email": email_ctx # Pass email if known, or let logic handle it
            }
            
            try:
                start_ts = time.time()
                res = requests.post(URL, json=payload)
                latency = (time.time() - start_ts) * 1000
                
                if res.status_code == 200:
                    data = res.json()
                    response_text = data.get("response", "[No Response]")
                    
                    # Log to Console
                    print(f"  Turn {turn_idx+1}: {user_input[:30]}... -> {latency:.0f}ms")
                    
                    # Append to Markdown Log
                    log_buffer += f"### Turn {turn_idx+1}\n"
                    log_buffer += f"**User:** {user_input}\n\n"
                    log_buffer += f"**Sarah ({latency:.0f}ms):**\n{response_text}\n\n"
                    log_buffer += "---\n"
                    
                else:
                    print(f"  ERROR: HTTP {res.status_code}")
                    log_buffer += f"**ERROR:** HTTP {res.status_code}\n\n"
            
            except Exception as e:
                print(f"  CRITICAL ERROR: {e}")
                log_buffer += f"**CRITICAL ERROR:** {e}\n\n"

        # Write Scenario to File
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_buffer)

    print(f"\nCompleted. Data logged to {LOG_FILE}")

if __name__ == "__main__":
    run_scenarios()
