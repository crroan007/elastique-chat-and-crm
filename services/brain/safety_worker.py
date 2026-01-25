from langchain_core.messages import AIMessage, HumanMessage
from services.safety_service import SafetyService
from services.brain.schemas import AgentState

def safety_worker(state: AgentState) -> dict:
    """
    Middleware worker that checks for critical safety violations.
    Transitions to 'END' if unsafe, otherwise passes control to 'supervisor'.
    """
    # 1. Get last user message
    messages = state.get("messages", [])
    if not messages:
        return {"next_node": "supervisor"} # No messages to check

    last_message = messages[-1]
    
    # Only check Human messages
    if isinstance(last_message, HumanMessage) or (isinstance(last_message, dict) and last_message.get("type") == "human"):
        text = last_message.content if hasattr(last_message, "content") else last_message.get("content", "")
        
        # 2. Check Safety
        safety_alert = SafetyService.check_emergency(text)
        
        if safety_alert:
            # STOP! Emergency detected.
            # Convert to AIMessage if needed for consistency, but standard State update works best
            system_refusal = AIMessage(content=safety_alert)
            return {
                "messages": [system_refusal],
                "next_node": "END", # Signal to graph to stop
                "error": "Safety Violation"
            }

    # 3. All clear - Pass to supervisor
    return {"next_node": "supervisor"}
