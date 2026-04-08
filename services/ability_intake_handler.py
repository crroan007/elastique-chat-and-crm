"""
Adaptive Protocol System - Ability Intake Handler
Handles the ability intake conversation flow with checkbox-style questions.

Refactored: Universal parser + data-driven stage routing.
"""
from typing import Dict, List, Optional, Tuple, Union
from services.schemas import UserAbilityProfile
from services.ability_constants import (
    ABILITY_TIERS, EXERCISE_TOLERANCE, PREGNANCY_TRIMESTERS,
    ACCESSIBILITY_OPTIONS, CONFLICTING_COMBINATIONS,
    HEALTH_STATUS_CHECKBOXES, MOBILITY_CHECKBOXES,
    TOLERANCE_OPTIONS, TRIMESTER_OPTIONS, SIDE_OPTIONS,
    WHEELCHAIR_ARMS_OPTIONS,
)
import re


# ==========================================
# KEYWORD MAPS (extracted from old parsers)
# ==========================================

HEALTH_KEYWORDS = {
    "cardiac": "cardiac_pulm", "heart": "cardiac_pulm", "lung": "cardiac_pulm",
    "copd": "cardiac_pulm", "asthma": "cardiac_pulm",
    "blood pressure": "cardiac_pulm", "hypertension": "cardiac_pulm", "pressure": "cardiac_pulm",
    "stroke": "cardiac_pulm", "diabetes": "cardiac_pulm", "diabetic": "cardiac_pulm",
    "sedentary": "sedentary", "desk": "sedentary", "recovering": "sedentary",
    "pregnant": "pregnant", "pregnancy": "pregnant", "expecting": "pregnant",
    "healthy": "average", "moderate": "average", "normal": "average",
    "athletic": "athletic", "athlete": "athletic", "performance": "athletic", "fit": "athletic",
    "limited": "limited_limbs", "limb": "limited_limbs", "missing": "limited_limbs",
    "skin": "average", "texture": "average",
}

MOBILITY_KEYWORDS = {
    "hand": "hands", "finger": "hands", "grip": "hands",
    "arm": "arms", "shoulder": "arms",
    "leg": "legs", "foot": "legs", "feet": "legs", "ankle": "legs", "knee": "legs", "hip": "legs",
    "wheelchair": "wheelchair", "chair": "wheelchair",
    "balance": "balance", "standing": "balance", "dizzy": "balance", "vertigo": "balance",
    "pain": "pain", "fatigue": "pain", "tired": "pain", "chronic": "pain",
    "back": "pain", "neck": "pain", "spine": "pain", "sciatica": "pain", "lumbar": "pain",
}


# ==========================================
# UNIVERSAL PARSER
# ==========================================

def parse_selection(
    msg: str,
    options: List[Dict],
    mode: str = "single",
    none_id: str = None,
    default_id: str = None,
    keyword_map: Dict[str, str] = None,
) -> Union[str, List[str], None]:
    """
    Universal parser for all intake questions.

    Args:
        msg: Raw user message
        options: List of {"id": ..., "label": ...} dicts (e.g. MOBILITY_CHECKBOXES)
        mode: "single" (returns str) or "multi" (returns List[str])
        none_id: ID treated as "no selection" (e.g. "none" for mobility)
        default_id: Fallback if nothing matches (e.g. "average" for health)
        keyword_map: Optional extra keywords {"heart": "cardiac_pulm"}

    Returns:
        mode="single": str (selected ID) or None (unrecognized)
        mode="multi":  List[str] (selected IDs, may be []) or None (unrecognized)
    """
    if not msg:
        return None

    msg_lower = msg.strip().lower()
    selected = []
    found_none = False

    # ----- PRIORITY 1: Number-index match (widget always sends numbers) -----
    numbers = re.findall(r'\d+', msg)
    for num_str in numbers:
        idx = int(num_str) - 1  # 1-indexed
        if 0 <= idx < len(options):
            opt_id = options[idx]["id"]
            if none_id and opt_id == none_id:
                found_none = True
            else:
                if opt_id not in selected:
                    selected.append(opt_id)

    # If we got number matches, return early (widget input is authoritative)
    if selected or found_none:
        if mode == "single":
            return selected[0] if selected else (default_id or None)
        else:
            return selected  # [] if only "none" was selected

    # ----- PRIORITY 2: Keyword map match (free-text fallback) -----
    if keyword_map:
        for keyword, mapped_id in keyword_map.items():
            if keyword in msg_lower and mapped_id not in selected:
                if none_id and mapped_id == none_id:
                    found_none = True
                else:
                    selected.append(mapped_id)

    if selected or found_none:
        if mode == "single":
            return selected[0] if selected else (default_id or None)
        else:
            return selected

    # ----- PRIORITY 3: Label text match (user typed the option text) -----
    for opt in options:
        label_lower = opt["label"].lower()
        opt_id = opt["id"]
        # Check if key parts of the label appear in the message
        label_words = [w for w in label_lower.split() if len(w) > 2]
        if any(w in msg_lower for w in label_words):
            if none_id and opt_id == none_id:
                found_none = True
            elif opt_id not in selected:
                selected.append(opt_id)

    if selected or found_none:
        if mode == "single":
            return selected[0] if selected else (default_id or None)
        else:
            return selected

    # ----- PRIORITY 4: Affirmative/none detection -----
    if any(w in msg_lower for w in ["none", "nothing", "n/a", "skip", "no issues"]):
        if mode == "multi":
            return []  # Explicit "no items"
        elif default_id:
            return default_id

    # ----- PRIORITY 5: Default fallback -----
    if default_id:
        # For health status: affirmative words default to "average"
        if any(w in msg_lower for w in ["fine", "good", "ok", "okay", "yes"]):
            return default_id if mode == "single" else [default_id]

    # Unrecognized
    return None


class AbilityIntakeHandler:
    """
    Handles the ability intake portion of the conversation flow.
    Collects health status, mobility considerations, and follow-up details.
    """

    # ==========================================
    # QUESTION GENERATORS (unchanged look/feel)
    # ==========================================

    @staticmethod
    def get_permission_message() -> str:
        """Stage 3: Permission + Intake Prep message."""
        return (
            "My role is to design **wellness protocols uniquely tailored to your specific needs**.\n\n"
            "To create the most personalized routine for you, I'll ask:\n"
            "• **A few quick questions** about your health and mobility\n"
            "• **A few short follow-ups** based on your answers\n\n"
            "This takes **less than 4 minutes** and ensures your protocol is perfectly matched to your body.\n\n"
            "**Ready to get started?**"
        )

    @staticmethod
    def get_health_status_question() -> str:
        """Stage 4A: Health Status checkbox question."""
        options = "\n".join([f"□ {opt['label']}" for opt in HEALTH_STATUS_CHECKBOXES])
        return (
            "**Which best describes your current health?** *(Select all that apply)*\n\n"
            f"{options}\n\n"
            "*Type the numbers or names of all that apply, then press Enter.*"
        )

    @staticmethod
    def get_mobility_question() -> str:
        """Stage 4B: Mobility Considerations checkbox question."""
        options = "\n".join([f"□ {opt['label']}" for opt in MOBILITY_CHECKBOXES])
        return (
            "**Do any mobility considerations apply to you?**\n\n"
            f"{options}\n\n"
            "*Type the numbers or names of all that apply, or 'none' to skip.*"
        )

    @staticmethod
    def get_wheelchair_arms_question() -> str:
        """Follow-up for wheelchair users: determine arm/hand use."""
        options = "\n".join([f"○ {opt['label']}" for opt in WHEELCHAIR_ARMS_OPTIONS])
        return (
            "**Do you have functional use of your arms/hands?**\n\n"
            f"{options}"
        )

    @staticmethod
    def get_tolerance_question() -> str:
        """Follow-up for cardiac/sedentary: exercise tolerance."""
        options = "\n".join([f"○ {opt['label']}" for opt in TOLERANCE_OPTIONS])
        return (
            "**What's your current exercise tolerance?**\n\n"
            f"{options}"
        )

    @staticmethod
    def get_trimester_question() -> str:
        """Follow-up for pregnant: which trimester."""
        options = "\n".join([f"○ {opt['label']}" for opt in TRIMESTER_OPTIONS])
        return (
            "**Which trimester are you in?**\n\n"
            f"{options}"
        )

    # SIDE QUESTIONS REMOVED

    # ==========================================
    # UNIVERSAL PARSING (delegates to parse_selection)
    # ==========================================

    @staticmethod
    def parse_health_status_response(msg: str) -> List[str]:
        """Parse user's health status checkbox selections."""
        result = parse_selection(
            msg, HEALTH_STATUS_CHECKBOXES,
            mode="multi", none_id="none", keyword_map=HEALTH_KEYWORDS
        )
        return result


    @staticmethod
    def parse_mobility_response(msg: str) -> Optional[List[str]]:
        """Parse user's mobility checkbox selections."""
        return parse_selection(
            msg, MOBILITY_CHECKBOXES,
            mode="multi", none_id="none", keyword_map=MOBILITY_KEYWORDS
        )

    @staticmethod
    def parse_wheelchair_arms_response(msg: str) -> Optional[str]:
        """Parse wheelchair arm-use response."""
        return parse_selection(msg, WHEELCHAIR_ARMS_OPTIONS, mode="single")


    @staticmethod
    def parse_tolerance_response(msg: str) -> Optional[str]:
        """Parse exercise tolerance selection. All options are valid (including 'none' = zero capacity)."""
        return parse_selection(msg, TOLERANCE_OPTIONS, mode="single")


    @staticmethod
    def parse_trimester_response(msg: str) -> Optional[str]:
        """Parse pregnancy trimester selection."""
        return parse_selection(msg, TRIMESTER_OPTIONS, mode="single", none_id="2nd")


    # SIDE PARSER REMOVED


    # ==========================================
    # CONFLICT DETECTION
    # ==========================================

    @staticmethod
    def detect_conflicts(health_status: List[str], mobility: List[str]) -> Optional[Dict]:
        """Check for conflicting selections and return clarification question if needed."""
        all_selections = health_status + mobility
        for conflict in CONFLICTING_COMBINATIONS:
            if all(item in all_selections for item in conflict["items"]):
                return {
                    "clarification": conflict["clarification"],
                    "options": conflict["resolution_options"]
                }
        return None

    # ==========================================
    # DETERMINE NEXT STEP
    # ==========================================

    @staticmethod
    def get_required_followups(profile: UserAbilityProfile) -> List[str]:
        """
        Determine which follow-up questions are still needed.
        Returns list of: 'tolerance', 'trimester', 'side_arms', 'side_legs', 'wheelchair_arms'
        """
        followups = []
        tier = profile.tier

        if tier in ["cardiac_pulm", "sedentary"] and not profile.exercise_tolerance:
            followups.append("tolerance")

        if tier == "pregnant" and not profile.pregnancy_trimester:
            followups.append("trimester")

        accessibility = profile.accessibility_needs
        details = profile.accessibility_details

        if "wheelchair" in accessibility:
            wheelchair_details = details.get("wheelchair", {})
            if not wheelchair_details.get("arm_use"):
                followups.append("wheelchair_arms")

        # SIDE FOLLOWUPS REMOVED

        return followups

    @staticmethod
    def build_profile_summary(profile: UserAbilityProfile) -> str:
        """Generate a human-readable summary of the ability profile."""
        parts = []

        if profile.tier:
            tier_info = ABILITY_TIERS.get(profile.tier, {})
            parts.append(f"**Health:** {tier_info.get('display', profile.tier)}")

        if profile.exercise_tolerance:
            tol_info = EXERCISE_TOLERANCE.get(profile.exercise_tolerance, {})
            parts.append(f"**Exercise Tolerance:** {tol_info.get('display', profile.exercise_tolerance)}")

        if profile.pregnancy_trimester:
            tri_info = PREGNANCY_TRIMESTERS.get(profile.pregnancy_trimester, {})
            parts.append(f"**Trimester:** {tri_info.get('display', profile.pregnancy_trimester)}")

        if profile.accessibility_needs:
            needs = []
            for need in profile.accessibility_needs:
                opt_info = ACCESSIBILITY_OPTIONS.get(need, {})
                label = opt_info.get("display", need)
                if need == "wheelchair":
                    arm_use = profile.accessibility_details.get("wheelchair", {}).get("arm_use")
                    if arm_use == "no":
                        label += " (no arm use)"
                    elif arm_use == "yes":
                        label += " (arms usable)"
                needs.append(label)
            parts.append(f"**Mobility:** {', '.join(needs)}")

        if not parts:
            return "Standard protocols"

        return "\n".join(parts)

    @staticmethod
    def get_intake_complete_message(profile: UserAbilityProfile, user_name: str, goal_options: str = "", ready_to_generate: bool = False) -> str:
        """
        Message shown when ability intake is complete.
        Summarizes profile and transitions to discovery or protocol generation.
        """
        summary = AbilityIntakeHandler.build_profile_summary(profile)

        if ready_to_generate:
            return (
                f"Thanks {user_name}! Here's your profile:\n\n"
                f"{summary}\n\n"
                f"I have everything I need. Building your personalized protocol now..."
            )

        return (
            f"Thanks {user_name}! Here's your profile:\n\n"
            f"{summary}\n\n"
            f"Now let's dig into the details so I can build your personalized protocol."
        )
