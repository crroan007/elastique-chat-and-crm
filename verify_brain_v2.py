from services.brain.supervisor import supervisor_worker
from services.brain.schemas import AgentState
from langchain_core.messages import HumanMessage
import os
from dotenv import load_dotenv

load_dotenv()

def test_supervisor():
    print("--- Testing Supervisor Agent (Gemini 1.5 Flash) ---")
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIPPING: No GOOGLE_API_KEY found.")
        return

    # CASE 1: Clinical
    print("\nCase 1: 'My leg is swelling'")
    state_clinical: AgentState = {
        "messages": [HumanMessage(content="My leg is swelling badly after the flight")],
        "user_profile": {},
        "context": {},
        "next_node": None,
        "error": None
    }
    result_clinical = supervisor_worker(state_clinical)
    print(f"Result Next Node: {result_clinical.get('next_node')}")
    if result_clinical.get("error"):
        print(f"SUPERVISOR ERROR: {result_clinical.get('error')}")
    assert result_clinical["next_node"] in ["clinical_worker", "protocol_worker"], f"Expected clinical, got {result_clinical.get('next_node')}"
    print("PASS: Clinical Intent")

    # CASE 2: CRM
    print("\nCase 2: 'Restart chat'")
    state_crm: AgentState = {
        "messages": [HumanMessage(content="Can I restart the chat?")],
        "user_profile": {},
        "context": {},
        "next_node": None,
        "error": None
    }
    result_crm = supervisor_worker(state_crm)
    print(f"Result Next Node: {result_crm.get('next_node')}")
    assert result_crm["next_node"] == "crm_worker", f"Expected crm_worker, got {result_crm.get('next_node')}"
    print("PASS: CRM Intent")

    # CASE 3: General
    print("\nCase 3: 'Hello there'")
    state_general: AgentState = {
        "messages": [HumanMessage(content="Hello there")],
        "user_profile": {},
        "context": {},
        "next_node": None,
        "error": None
    }
    result_general = supervisor_worker(state_general)
    print(f"Result Next Node: {result_general.get('next_node')}")
    assert result_general["next_node"] == "general_worker", f"Expected general_worker, got {result_general.get('next_node')}"
    print("PASS: General Intent")

if __name__ == "__main__":
    try:
        test_supervisor()
        print("\nAll Tests Passed!")
    except Exception as e:
        print(f"\nFAILED: {e}")
        exit(1)
