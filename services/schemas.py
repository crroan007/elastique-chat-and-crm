from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional, Any
from datetime import datetime


class UserAbilityProfile(BaseModel):
    """
    Ability profile for adaptive protocol generation.
    Captures health tier, tolerance, and accessibility needs.
    """
    tier: Optional[str] = None  # cardiac_pulm, sedentary, pregnant, average, athletic
    exercise_tolerance: Optional[str] = None  # none, little, moderate, high (for cardiac/sedentary)
    pregnancy_trimester: Optional[str] = None  # t1, t2, t3 (for pregnant tier)
    accessibility_needs: List[str] = Field(default_factory=list)  # hands, arms, legs, wheelchair, balance, pain
    accessibility_details: Dict[str, Any] = Field(default_factory=dict)  # {hands: {side: "right"}, legs: {side: "both"}}
    has_limb_limitations: bool = False # Flag for "Limited use of limbs" modifier
    intake_completed: bool = False


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
    goal_key: Optional[str] = None  # lighter | postop | skin | recovery | pregnancy | travel | wellness
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
    pending_pdf_generation: bool = False  # Flag to enable two-message PDF delivery
    extra_context: Optional[str] = None
    last_question_key: Optional[str] = None
    question_attempts: Dict[str, int] = Field(default_factory=dict)
    discovery_slots: Dict[str, bool] = Field(default_factory=dict)
    protocol_items: List[Dict[str, Any]] = Field(default_factory=list)
    empathy_mode: str = "restorative" # "restorative" or "performance"
    refinement_count: int = 0
    agreed_protocol: List[str] = Field(default_factory=list)
    active_protocol_data: Optional[Dict[str, Any]] = None  # Mutable protocol state
    preferences: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    # Adaptive Protocol System
    ability_profile: Optional[UserAbilityProfile] = None
    ability_intake_stage: Optional[str] = None  # health_status, mobility, follow_up
    intake_reprompt_count: int = 0  # retry guard for intake questions
    pending_ability_followup: Optional[str] = None  # tolerance, trimester, side_clarification

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
