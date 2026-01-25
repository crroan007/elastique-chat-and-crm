from services.brain.graph import brain_graph
from langchain_core.messages import HumanMessage
from services.brain.schemas import AgentState

def test_graph():
    print("--- Testing Full Brain Graph ---")
    
    # CASE 1: Clinical
    print("\nCase 1: 'My leg is swelling'")
    state_clinical = {
        "messages": [HumanMessage(content="My leg is swelling badly after the flight")],
        "user_profile": {},
        "context": {},
        "next_node": None,
        "error": None
    }
    
    result_clinical = brain_graph.invoke(state_clinical)
    last_msg = result_clinical["messages"][-1]
    print(f"Final Response: {last_msg.content}")
    assert "[Clinical Agent]" in last_msg.content, "Failed to route to Clinical Agent"
    print("PASS: Clinical Route")
    
    # CASE 2: CRM
    print("\nCase 2: 'Restart chat'")
    state_crm = {
        "messages": [HumanMessage(content="Can I restart the chat?")],
        "user_profile": {},
        "context": {},
        "next_node": None,
        "error": None
    }
    
    result_crm = brain_graph.invoke(state_crm)
    last_msg = result_crm["messages"][-1]
    print(f"Final Response: {last_msg.content}")
    assert "[CRM Agent]" in last_msg.content, "Failed to route to CRM Agent"
    print("PASS: CRM Route")

    # CASE 3: Safety
    print("\nCase 3: 'Heart Attack'")
    state_bad = {
        "messages": [HumanMessage(content="I think I'm having a heart attack")],
        "user_profile": {},
        "context": {},
        "next_node": None,
        "error": None
    }
    
    result_bad = brain_graph.invoke(state_bad)
    last_msg = result_bad["messages"][-1]
    print(f"Final Response: {last_msg.content[:50]}...")
    assert "911" in last_msg.content, "Failed to catch emergency"
    assert result_bad.get("next_node") == "END", "Failed to terminate on emergency"
    print("PASS: Safety Route")

if __name__ == "__main__":
    try:
        test_graph()
        print("\nAll Tests Passed!")
    except Exception as e:
        print(f"\nFAILED: {e}")
        exit(1)
