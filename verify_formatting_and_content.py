import requests
import json
import time

BASE_URL = "http://localhost:8000"

def verify_response():
    print("--- Starting Verification: Formatting & Content ---")
    
    import uuid
    session_id = str(uuid.uuid4())
    print(f"   Generated Local Session ID: {session_id}")

    # 1. Start Session (Warmup)
    # We don't check session_id here, we use our own.
    try:
        requests.post(f"{BASE_URL}/chat", json={"message": "Hi, I'm verifying formatting.", "session_id": session_id})
    except Exception as e:
        print(f"FAILED: Connection Error: {e}")
        return

    # 2. Provide Identity + Context (to bypass identity_capture AND trigger specific protocol)
    print("2. Providing Identity + Context...")
    resp_ident = requests.post(f"{BASE_URL}/chat", json={
        "session_id": session_id,
        "message": "My name is Sarah Jones, email sarah@example.com, and my legs are swollen.",
        "user_email": "sarah@example.com"
    })
    
    bot_response = resp_ident.json().get("response", "")
    print(f"\n[Bot Response Preview]:\n{bot_response[:300]}...\n")
    
    print(f"\n[Bot Response Preview]:\n{bot_response[:300]}...\n")

    # 3. Assertions
    errors = []
    
    # Check for Dosage
    if "*Dose:*" in bot_response:
        print("PASS: Dosage information detected.")
    else:
        errors.append("Missing '*Dose:*' field.")

    # Check for Evidence Level
    if "Evidence Level" in bot_response:
        print("PASS: Evidence Level detected.")
    else:
        errors.append("Missing 'Evidence Level' field.")

    # Check for Markdown Source Link
    if "[Source](" in bot_response:
        print("PASS: Markdown Source link detected.")
    else:
        errors.append("Missing Markdown link '[Source]('")

    # Check for Accidentally leaked HTML
    if "<a href=" in bot_response:
        errors.append("FAILED: Raw HTML '<a>' tag found in response (Should be Markdown).")
    else:
        print("PASS: No raw HTML anchor tags found.")

    # Write results to file
    with open("verification_result.log", "w", encoding="utf-8") as f:
        f.write("-" * 30 + "\n")
        f.write(f"Bot Response Preview:\n{bot_response}\n")
        f.write("-" * 30 + "\n")
        
        if errors:
            f.write("\n--- VERIFICATION FAILED ---\n")
            for err in errors:
                f.write(f" - {err}\n")
        else:
            f.write("\n--- VERIFICATION PASSED ---\n")
            f.write("The bot is correctly serving Dosage, Evidence, and valid Markdown citations.\n")

    if errors:
        print("\n--- VERIFICATION FAILED ---")
        for err in errors:
            print(f" - {err}")
    else:
        print("\n--- VERIFICATION PASSED ---")


if __name__ == "__main__":
    # Give server a moment to settle if it just restarted
    time.sleep(2)
    verify_response()
