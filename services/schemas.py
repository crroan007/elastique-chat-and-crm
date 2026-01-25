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
