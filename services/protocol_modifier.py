"""
Protocol Modifier
Applies ability-based multipliers and accessibility filters to protocols.
Used by _handle_diagnosis_v3 to personalize recommendations.
"""
from typing import Dict, List, Optional, Tuple
import re
from services.ability_constants import (
    ABILITY_TIERS, EXERCISE_TOLERANCE, PREGNANCY_TRIMESTERS,
    ACCESSIBILITY_OPTIONS, calculate_dose_multiplier
)
from services.schemas import UserAbilityProfile
from services.enterprise_logging import enterprise_logger


class ProtocolModifier:
    """
    Modifies clinical protocols based on user's ability profile.
    - Applies dose multipliers (0.3x → 1.5x)
    - Filters exercises by accessibility constraints
    - Adds pregnancy-safe modifications
    """
    
    # Exercises and what they require (these map to exclusion tags in ACCESSIBILITY_OPTIONS)
    EXERCISE_REQUIREMENTS = {
        "Structured Calf Pump": ["leg_exercises", "standing"],
        "Standing Calf Raises": ["leg_exercises", "standing"],
        "Leg Elevation": [],  # Safe for all (passive)
        "Afternoon Walk": ["walking", "leg_exercises"],
        "Aerobic Movement": ["walking", "leg_exercises"],
        "Seated Ankle Pumps": ["leg_exercises"],
        "Arm Ergometer / Wheelchair Push": ["arm_pumping"],
        "Diaphragmatic Breathing": [],  # Safe for all
        "Supraclavicular MLD": [],  # Safe for all
        "Arm Circles": ["arm_circles"],
        "Overhead Stretch": ["overhead_movements"],
        "Upper Body Pump Circuit": ["arm_pumping", "arm_circles", "overhead_movements"],
        "Safety First MLD": [],  # Safe for all
    }
    
    # Exercises unsafe during pregnancy by trimester
    PREGNANCY_CONTRAINDICATIONS = {
        "t2": ["supine_after_20_weeks"],  # Avoid lying flat on back
        "t3": ["supine", "high_impact", "abdominal_pressure"]
    }
    
    # Alternative exercises when original is contraindicated
    ALTERNATIVES = {
        "Legs Up The Wall": {
            "condition": "pregnant_t3",
            "alternative": "Side-Lying Leg Elevation",
            "instruction": "Lie on left side with pillow between knees, elevate top leg"
        },
        "Structured Calf Pump": [
            {
                "condition": "wheelchair",
                "alternative": "Seated Ankle Pumps",
                "instruction": "Flex and point ankles while seated, 20-30 reps"
            },
            {
                "condition": "balance",
                "alternative": "Seated Ankle Pumps",
                "instruction": "Sit tall and flex/point ankles, 20-30 reps"
            }
        ],
        "Afternoon Walk": [
            {
                "condition": "wheelchair",
                "alternative": "Arm Ergometer / Wheelchair Push",
                "instruction": "20-30 min continuous arm movement"
            },
            {
                "condition": "balance",
                "alternative": "Seated Marching",
                "instruction": "Seated march with gentle arm swings, 10-15 min"
            }
        ],
        "Aerobic Movement": [
            {
                "condition": "balance",
                "alternative": "Seated Marching",
                "instruction": "Seated march with gentle arm swings, 10-20 min"
            },
            {
                "condition": "wheelchair",
                "alternative": "Arm Ergometer / Wheelchair Push",
                "instruction": "20-30 min continuous arm movement"
            },
            {
                "condition": "legs",
                "alternative": "Seated Upper-Body Cardio",
                "instruction": "Seated arm swings or shadow boxing, 10-20 min"
            }
        ]
    }
    
    @staticmethod
    def modify_protocol(
        protocol_items: List[Dict],
        ability_profile: Optional[UserAbilityProfile],
        session_id: str = None
    ) -> List[Dict]:
        """
        Apply ability-based modifications to a protocol.
        
        Args:
            protocol_items: List of protocol items with name, instruction, dose
            ability_profile: User's ability profile (tier, tolerance, accessibility)
            session_id: For logging
        
        Returns:
            Modified list of protocol items
        """
        if not ability_profile:
            return protocol_items
        
        # Calculate overall multiplier by extracting individual fields
        tolerance_or_trimester = ability_profile.exercise_tolerance or ability_profile.pregnancy_trimester
        multiplier = calculate_dose_multiplier(
            ability_tier=ability_profile.tier,
            tolerance_or_trimester=tolerance_or_trimester,
            accessibility_needs=ability_profile.accessibility_needs
        )
        
        # Log the multiplier being applied
        if session_id:
            enterprise_logger.info(
                f"Applying dose multiplier {multiplier:.2f}x",
                session_id=session_id,
                event_type="protocol_modification",
                ability_tier=ability_profile.tier,
                multiplier=multiplier
            )
        
        modified_items = []
        
        for item in protocol_items:
            # Check accessibility constraints
            filtered_item = ProtocolModifier._filter_by_accessibility(
                item, ability_profile
            )
            
            if filtered_item is None:
                # Exercise was filtered out, try alternative
                alt_item = ProtocolModifier._get_alternative(item, ability_profile)
                if alt_item:
                    modified_items.append(alt_item)
                continue
            
            # Apply dose multiplier
            modified_item = ProtocolModifier._apply_dose_multiplier(
                filtered_item, multiplier
            )
            
            # Add pregnancy modifications if applicable
            if ability_profile.pregnancy_trimester:
                modified_item = ProtocolModifier._add_pregnancy_notes(
                    modified_item, ability_profile.pregnancy_trimester
                )
            
            modified_items.append(modified_item)

        # Wheelchair support add-ons (breathing + assisted + compression)
        if ProtocolModifier._is_wheelchair(ability_profile):
            arm_use = ProtocolModifier._get_wheelchair_arm_use(ability_profile)
            modified_items = ProtocolModifier._ensure_wheelchair_support_items(modified_items, arm_use=arm_use)

        # Wheelchair with no arm use: fully assisted, passive-only routine
        if ProtocolModifier._is_wheelchair_no_arm(ability_profile):
            modified_items = ProtocolModifier._apply_wheelchair_no_arm_protocol(modified_items)

        # Add foam rolling for moderately active or athletic users
        if ability_profile and ability_profile.tier in {"average", "athletic"}:
            modified_items = ProtocolModifier._ensure_foam_rolling(modified_items)

        # Add assisted manual rolling/massage when arms or legs are not mobile
        assisted_limbs = []
        if ability_profile and ProtocolModifier._needs_assisted_manual(ability_profile, "arms"):
            assisted_limbs.append("arms")
        if ability_profile and ProtocolModifier._needs_assisted_manual(ability_profile, "legs"):
            assisted_limbs.append("legs")
        if assisted_limbs:
            modified_items = ProtocolModifier._ensure_assisted_manual_items(modified_items, assisted_limbs)

        return modified_items

    @staticmethod
    def _is_wheelchair_no_arm(profile: UserAbilityProfile) -> bool:
        if not profile:
            return False
        details = profile.accessibility_details.get("wheelchair", {})
        return "wheelchair" in profile.accessibility_needs and details.get("arm_use") == "no"

    @staticmethod
    def _is_wheelchair(profile: UserAbilityProfile) -> bool:
        if not profile:
            return False
        return "wheelchair" in profile.accessibility_needs

    @staticmethod
    def _get_wheelchair_arm_use(profile: UserAbilityProfile) -> Optional[str]:
        if not profile:
            return None
        return profile.accessibility_details.get("wheelchair", {}).get("arm_use")

    @staticmethod
    def _needs_assisted_manual(profile: UserAbilityProfile, limb: str) -> bool:
        if not profile:
            return False
        details = profile.accessibility_details.get(limb, {})
        function = (details.get("function") or details.get("use") or details.get("ability") or "").lower()
        if function in {"none", "no", "no_use", "unable", "cannot", "cant"}:
            return True
        if limb == "arms":
            arm_use = profile.accessibility_details.get("wheelchair", {}).get("arm_use")
            if arm_use == "no":
                return True
        return False

    @staticmethod
    def _ensure_wheelchair_support_items(items: List[Dict], arm_use: Optional[str] = None) -> List[Dict]:
        """
        Ensure wheelchair-appropriate support items are included.
        """
        updated = list(items)

        def has_name(fragment: str) -> bool:
            fragment = fragment.lower()
            return any(fragment in (i.get("name", "").lower()) for i in updated)

        if not has_name("breathing"):
            updated.append({
                "name": "Diaphragmatic (Thoracic) Breathing",
                "instruction": "Slow inhale so the belly expands, long exhale to support the thoracic pump.",
                "dose": "5 min/day (or 2-3 min, 2x/day)"
            })

        if not has_name("assisted"):
            updated.append({
                "name": "Assisted Lymphatic Support",
                "instruction": "If available, use gentle manual lymphatic strokes or soft-bristle brushing toward the torso.",
                "dose": "10-15 min, as tolerated"
            })

        if not has_name("compression"):
            updated.append({
                "name": "Compression Support",
                "instruction": "Use properly fitted compression garments as prescribed or recommended by your clinician.",
                "dose": "As prescribed"
            })

        return updated

    @staticmethod
    def _ensure_foam_rolling(items: List[Dict]) -> List[Dict]:
        """
        Add foam rolling when appropriate for active users.
        """
        updated = list(items)

        def has_name(fragment: str) -> bool:
            fragment = fragment.lower()
            return any(fragment in (i.get("name", "").lower()) for i in updated)

        if not has_name("foam"):
            updated.append({
                "name": "Foam Rolling (Manual Rolling)",
                "instruction": "Slow, gentle passes over legs/arms; avoid pain or bruising.",
                "dose": "5-10 min, 3x/week"
            })

        return updated

    @staticmethod
    def _ensure_assisted_manual_items(items: List[Dict], limbs: List[str]) -> List[Dict]:
        """
        Add assisted manual rolling and massage when limbs are not mobile.
        """
        updated = list(items)

        def has_name(fragment: str) -> bool:
            fragment = fragment.lower()
            return any(fragment in (i.get("name", "").lower()) for i in updated)

        if "legs" in limbs:
            if not has_name("assisted manual rolling (legs)"):
                updated.append({
                    "name": "Assisted Manual Rolling (Legs)",
                    "instruction": "Caregiver performs gentle rolling toward the torso on affected leg(s).",
                    "dose": "10-15 min, 2-3x/week"
                })
            if not has_name("assisted manual massage (legs)"):
                updated.append({
                    "name": "Assisted Manual Massage (Legs)",
                    "instruction": "Light manual massage toward the torso on affected leg(s); avoid deep pressure.",
                    "dose": "10-15 min, 2-3x/week"
                })

        if "arms" in limbs:
            if not has_name("assisted manual rolling (arms)"):
                updated.append({
                    "name": "Assisted Manual Rolling (Arms)",
                    "instruction": "Caregiver performs gentle rolling toward the torso on affected arm(s).",
                    "dose": "10-15 min, 2-3x/week"
                })
            if not has_name("assisted manual massage (arms)"):
                updated.append({
                    "name": "Assisted Manual Massage (Arms)",
                    "instruction": "Light manual massage toward the torso on affected arm(s); avoid deep pressure.",
                    "dose": "10-15 min, 2-3x/week"
                })

        return updated

    @staticmethod
    def _apply_wheelchair_no_arm_protocol(items: List[Dict]) -> List[Dict]:
        """
        Keep only passive items and add a fully assisted breathing + support set.
        """
        passive = []
        for item in items:
            reqs = ProtocolModifier.EXERCISE_REQUIREMENTS.get(item.get("name", ""), [])
            if not reqs:
                passive.append(item)

        passive = ProtocolModifier._ensure_wheelchair_support_items(passive, arm_use="no")
        return passive
    
    @staticmethod
    def _filter_by_accessibility(
        item: Dict,
        profile: UserAbilityProfile
    ) -> Optional[Dict]:
        """
        Check if exercise is suitable for user's accessibility needs.
        Returns None if filtered out, otherwise returns the item.
        """
        exercise_name = item.get("name", "")

        # Eligibility gating (e.g., average/athletic only)
        eligible_tiers = item.get("eligibility")
        if eligible_tiers and (not profile or profile.tier not in eligible_tiers):
            return None

        # Requires specific accessibility needs (e.g., arms/legs not mobile)
        required_access = item.get("requires_accessibility")
        if required_access:
            if not profile or not any(req in profile.accessibility_needs for req in required_access):
                return None

        # Requires specific accessibility details (e.g., function = none)
        required_details = item.get("requires_accessibility_detail")
        if required_details:
            if not profile:
                return None
            for limb, constraints in required_details.items():
                details = profile.accessibility_details.get(limb, {})
                for key, expected in (constraints or {}).items():
                    actual = details.get(key)
                    if str(actual).lower() != str(expected).lower():
                        return None
        
        # Get what this exercise requires (tags from EXERCISE_REQUIREMENTS)
        requirements = ProtocolModifier.EXERCISE_REQUIREMENTS.get(exercise_name, [])
        
        # Check each accessibility need
        for need in profile.accessibility_needs:
            need_config = ACCESSIBILITY_OPTIONS.get(need, {})
            
            # Get what this accessibility need excludes
            exclusions = need_config.get("excludes", [])  # Fixed: was 'excludes_exercises'
            
            # If any exercise requirement is in the exclusion list, filter it out
            for req in requirements:
                if req in exclusions:
                    return None
        
        return item
    
    @staticmethod
    def _get_alternative(
        item: Dict,
        profile: UserAbilityProfile
    ) -> Optional[Dict]:
        """
        Get alternative exercise when original is contraindicated.
        """
        exercise_name = item.get("name", "")
        alt_config = ProtocolModifier.ALTERNATIVES.get(exercise_name)

        if not alt_config:
            return None

        alt_configs = alt_config if isinstance(alt_config, list) else [alt_config]

        for candidate in alt_configs:
            condition = candidate.get("condition", "")

            # Accessibility-based alternatives (balance, wheelchair, etc.)
            if condition in profile.accessibility_needs:
                alt_item = {
                    "name": candidate["alternative"],
                    "instruction": candidate["instruction"],
                    "dose": item.get("dose", "As tolerated"),
                    "note": f"(Alternative for {exercise_name})"
                }
                return ProtocolModifier._filter_by_accessibility(alt_item, profile)

            # Pregnancy-specific alternatives
            if "pregnant" in condition and profile.pregnancy_trimester:
                trimester_match = f"pregnant_{profile.pregnancy_trimester}" == condition
                if trimester_match:
                    alt_item = {
                        "name": candidate["alternative"],
                        "instruction": candidate["instruction"],
                        "dose": item.get("dose", "As tolerated"),
                        "note": "(Safe alternative during pregnancy)"
                    }
                    return ProtocolModifier._filter_by_accessibility(alt_item, profile)

        return None

    # Practical minimums — anything below these is not a useful exercise
    MIN_DURATION_MINUTES = 2   # No exercise under 2 minutes
    MIN_REPS_PER_SET = 10      # No fewer than 10 reps per set
    MIN_RANGE_LOW_MINUTES = 3  # Range low end at least 3 minutes
    MIN_RANGE_SPAN = 3         # Range high must be at least 3 above low

    @staticmethod
    def _apply_dose_multiplier(item: Dict, multiplier: float) -> Dict:
        """
        Apply dose multiplier to exercise duration/reps.
        Handles formats like: "30 min", "3x20 reps", "15-20 min"
        Enforces practical minimums so no exercise is impractically short.
        """
        dose = item.get("dose", "")
        if not dose or multiplier == 1.0:
            return item

        modified_item = item.copy()
        original_dose = dose
        MIN_MIN = ProtocolModifier.MIN_DURATION_MINUTES
        MIN_REPS = ProtocolModifier.MIN_REPS_PER_SET
        MIN_RANGE_LOW = ProtocolModifier.MIN_RANGE_LOW_MINUTES
        MIN_RANGE_SPAN = ProtocolModifier.MIN_RANGE_SPAN

        # Pattern: "X-Y min" (range) — check BEFORE single min to avoid double-match
        range_match = re.search(r'(\d+)-(\d+)\s*(min|minute)', dose, re.IGNORECASE)
        if range_match:
            low = max(MIN_RANGE_LOW, int(int(range_match.group(1)) * multiplier))
            high = max(low + MIN_RANGE_SPAN, int(int(range_match.group(2)) * multiplier))
            dose = dose.replace(range_match.group(0), f"{low}-{high} min")
        else:
            # Pattern: "X min" or "X minutes" (single value)
            min_match = re.search(r'(\d+)\s*(min|minute)', dose, re.IGNORECASE)
            if min_match:
                original_val = int(min_match.group(1))
                new_val = max(MIN_MIN, int(original_val * multiplier))
                dose = dose.replace(min_match.group(0), f"{new_val} min")

        # Pattern: "Xx Y reps" (sets x reps)
        reps_match = re.search(r'(\d+)\s*[xX]\s*(\d+)\s*rep', dose, re.IGNORECASE)
        if reps_match:
            sets = int(reps_match.group(1))
            reps = int(reps_match.group(2))
            new_reps = max(MIN_REPS, int(reps * multiplier))
            dose = dose.replace(reps_match.group(0), f"{sets}x{new_reps} reps")

        # Pattern: standalone "X reps" without sets
        standalone_reps = re.search(r'(\d+)\s*rep', dose, re.IGNORECASE)
        if standalone_reps and not reps_match:
            reps = int(standalone_reps.group(1))
            new_reps = max(MIN_REPS, int(reps * multiplier))
            dose = dose.replace(standalone_reps.group(0), f"{new_reps} reps")

        modified_item["dose"] = dose

        # Add note if dose was reduced
        if multiplier < 1.0 and dose != original_dose:
            modified_item["adjustment_note"] = f"Adjusted from {original_dose}"

        return modified_item
    
    @staticmethod
    def _add_pregnancy_notes(item: Dict, trimester: str) -> Dict:
        """
        Add pregnancy-specific notes and modifications.
        """
        modified_item = item.copy()
        instruction = modified_item.get("instruction", "")
        
        if trimester == "t2":
            # After 20 weeks, avoid supine positions
            if "lie" in instruction.lower() or "supine" in instruction.lower():
                modified_item["instruction"] = instruction + " (Use side-lying after 20 weeks)"
        
        elif trimester == "t3":
            # Third trimester: shorter durations, side-lying only
            modified_item["instruction"] = instruction + " (Keep sessions shorter, side-lying preferred)"
            
            # Reduce duration further
            dose = modified_item.get("dose", "")
            min_match = re.search(r'(\d+)\s*min', dose)
            if min_match:
                original = int(min_match.group(1))
                reduced = max(ProtocolModifier.MIN_DURATION_MINUTES, int(original * 0.7))
                modified_item["dose"] = dose.replace(min_match.group(0), f"{reduced} min")
        
        return modified_item
    
    @staticmethod
    def get_protocol_summary_for_ability(profile: UserAbilityProfile) -> str:
        """
        Generate a summary of modifications being applied.
        """
        parts = []
        
        if profile.tier:
            tier_info = ABILITY_TIERS.get(profile.tier, {})
            parts.append(f"Adjusted for {tier_info.get('display', profile.tier)}")
        
        if profile.exercise_tolerance:
            parts.append(f"{profile.exercise_tolerance} exercise tolerance")
        
        if profile.pregnancy_trimester:
            tri_info = PREGNANCY_TRIMESTERS.get(profile.pregnancy_trimester, {})
            parts.append(tri_info.get('display', profile.pregnancy_trimester))
        
        if profile.accessibility_needs:
            parts.append(f"Modified for: {', '.join(profile.accessibility_needs)}")
        
        if not parts:
            return "Standard protocol"
        
        return "; ".join(parts)
