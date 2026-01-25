from services.brain.schemas import AgentState
from langchain_core.messages import AIMessage

# Placeholder Workers
# These will be replaced by actual Agent classes later

def clinical_worker(state: AgentState) -> dict:
    """Handles clinical queries using RAG + Protocols."""
    # TODO: Connect to ClinicalAgent
    # For now, return a placeholder
    return {
        "messages": [AIMessage(content="[Clinical Agent]: I am analyzing your symptoms based on the Stanford protocols.")],
        "next_node": "END"
    }

def protocol_worker(state: AgentState) -> dict:
    """Handles specific protocol requests."""
    # TODO: Connect to ProtocolAgent
    return {
        "messages": [AIMessage(content="[Protocol Agent]: Here is the protocol you requested.")],
        "next_node": "END"
    }

def crm_worker(state: AgentState) -> dict:
    """Handles account, scheduling, and admin tasks."""
    # TODO: Connect to CRMAgent
    return {
        "messages": [AIMessage(content="[CRM Agent]: I can help you update your account.")],
        "next_node": "END"
    }

def general_worker(state: AgentState) -> dict:
    """Handles general chit-chat."""
    # TODO: Connect to GeneralAgent
    return {
        "messages": [AIMessage(content="[General Agent]: Hello! How can I help you regarding your lymphatic health today?")],
        "next_node": "END"
    }
