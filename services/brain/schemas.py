from typing import TypedDict, Annotated, List, Optional, Literal
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages

# --- Core Data Models ---

class UserProfile(BaseModel):
    """Type-safe user profile structure."""
    name: Optional[str] = None
    email: Optional[str] = None
    marketing_segment: Optional[str] = None
    health_goal: Optional[str] = None
    
class ConversationContext(BaseModel):
    """Context governing behavioral adaptation."""
    current_intent: str = "general_chat"
    stress_score: float = 0.0
    detected_mood: str = "neutral"
    last_protocol_suggested: Optional[str] = None

# --- Graph State ---

class AgentState(TypedDict):
    """The central state object passed between graph nodes."""
    # Messages use standard LangChain add_messages reducer
    messages: Annotated[List, add_messages]
    
    # Structured State (Replace dicts with Models where possible or keep dicts for LangGraph compat)
    user_profile: UserProfile
    context: ConversationContext
    
    # Flow Control
    next_node: Optional[str]
    error: Optional[str]
