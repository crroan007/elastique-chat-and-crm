from services.brain.safety_worker import safety_worker
from services.brain.schemas import AgentState
from langchain_core.messages import HumanMessage, AIMessage

def test_safety_check():
    print("--- Testing Safety Worker ---")
    
    # CASE 1: Emergency
    print("\nCase 1: Heart Attack")
    state_bad: AgentState = {
        "messages": [HumanMessage(content="I think I'm having a heart attack right now")],
        "user_profile": {},
        "context": {},
        "next_node": None,
        "error": None
    }
    
    result_bad = safety_worker(state_bad)
    print(f"Result Next Node: {result_bad.get('next_node')}")
    
    # Check messages
    msgs = result_bad.get("messages", [])
    if msgs:
        print(f"Response: {msgs[0].content[:50]}...")
    
    assert result_bad["next_node"] == "END", "Failed to catch emergency"
    assert "911" in msgs[0].content, "Failed to provide emergency number"
    print("PASS: Emergency Caught")
    
    # CASE 2: Safe
    print("\nCase 2: General Chat")
    state_good: AgentState = {
        "messages": [HumanMessage(content="Hello, how can you help me?")],
        "user_profile": {},
        "context": {},
        "next_node": None,
        "error": None
    }
    
    result_good = safety_worker(state_good)
    print(f"Result Next Node: {result_good.get('next_node')}")
    
    assert result_good["next_node"] == "supervisor", "Failed to pass safe message"
    print("PASS: Safe Message Passed")

if __name__ == "__main__":
    try:
        test_safety_check()
        print("\nAll Tests Passed!")
    except Exception as e:
        print(f"\nFAILED: {e}")
        exit(1)
