from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional, Any
from datetime import datetime

class UserSessionState(BaseModel):
    """
    Enterprise-grade state model for a user session.
    Ensures type-safety and field validation across the cloud.
    """
    session_id: str
    stage: str = "identity_capture"
    user_name: Optional[str] = None
    user_email: Optional[EmailStr] = None
    temp_name: Optional[str] = None
    goal: Optional[str] = None  # protocol | shop | consult
    primary_region: Optional[str] = None
    context_trigger: Optional[str] = None
    timing: Optional[str] = None
    micro_values_used: List[str] = Field(default_factory=list)
    discovery_permission_asked: bool = False
    discovery_permission_granted: bool = False
    pending_context_default: bool = False
    pending_goal_default: bool = False
    pending_summary_confirmation: bool = False
    pending_summary_details: bool = False
    extra_context: Optional[str] = None
    last_question_key: Optional[str] = None
    question_attempts: Dict[str, int] = Field(default_factory=dict)
    empathy_mode: str = "restorative" # "restorative" or "performance"
    refinement_count: int = 0
    agreed_protocol: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)

class ProtocolItem(BaseModel):
    name: str
    instruction: str
    dose: str
    evidence: str
    urls: List[str] = Field(default_factory=list)

class ClinicalProtocol(BaseModel):
    title: str
    items: List[ProtocolItem]
    keywords: List[str] = Field(default_factory=list)
