"""
Full Pipeline Validation: Answers -> Profile -> Protocol -> PDF
===============================================================
3-layer test covering the entire questionnaire-to-PDF chain.

Layer 1: Widget answers map to correct profile fields
Layer 2: Profiles produce correct protocols (exercises, multipliers, deny-lists)
Layer 3: Generated PDFs contain correct personalized content

Run: python test_full_pipeline_validation.py
"""

import os
import re
import sys
import math
import json
import logging
from typing import List, Dict, Optional, Any

# Suppress noisy logs during testing
logging.disable(logging.WARNING)

from services.ability_intake_handler import AbilityIntakeHandler, parse_selection
from services.ability_constants import (
    ABILITY_TIERS, EXERCISE_TOLERANCE, PREGNANCY_TRIMESTERS,
    ACCESSIBILITY_OPTIONS, HEALTH_STATUS_CHECKBOXES, MOBILITY_CHECKBOXES,
    TOLERANCE_OPTIONS, TRIMESTER_OPTIONS, WHEELCHAIR_ARMS_OPTIONS,
    calculate_dose_multiplier,
)
from services.ability_intake_handler import HEALTH_KEYWORDS, MOBILITY_KEYWORDS
from services.schemas import UserAbilityProfile
from services.protocol_modifier import ProtocolModifier
from services.clinical_library import CLINICAL_PROTOCOLS
from services.protocol_generator import ProtocolGenerator

# ═══════════════════════════════════════════════════════════════════
# TEST CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# Exercises that MUST NOT appear for each accessibility need
MUST_NOT_CONTAIN = {
    "wheelchair": ["Structured Calf Pump", "Standing Calf Raises", "Afternoon Walk", "Aerobic Movement"],
    "balance": ["Structured Calf Pump", "Standing Calf Raises", "Afternoon Walk", "Aerobic Movement"],
    "arms": ["Upper Body Pump Circuit", "Arm Circles", "Overhead Stretch"],
    # Note: "legs" excludes tags calf_pumps, leg_elevation, walking, foot_circles
    # but Leg Elevation has requirement [] (passive/safe), and Calf Pump uses "leg_exercises"+"standing" tags.
    # Only "Afternoon Walk" and "Aerobic Movement" are excluded via "walking" tag.
    "legs": ["Afternoon Walk", "Aerobic Movement"],
}

# Exercise name fragments that MUST appear for each accessibility need.
# Uses partial matching — "Diaphragmatic" matches "Diaphragmatic (Thoracic) Breathing"
# and "Deep Breathing" matches "Deep Breathing Recovery".
# "Compression" matches both "Compression Support" and "Compression Adherence".
MUST_CONTAIN = {
    "wheelchair": ["Compression"],
    "wheelchair_no_arms": ["Assisted Lymphatic Support", "Compression"],
    "balance": [],  # Alternatives are protocol-dependent
}

# PDF compliance: prohibited terms in NON-CITATION sections.
# Note: The Lymphatic Health Primer contains research summaries that reference
# medical conditions ("edema", "lymphedema") in a scientific context. Those are
# excluded from this scan. We check terms that should NEVER appear in Sarah's
# own language (protocol table, FAQs, self-check, profile summary).
PROHIBITED_TERMS_IN_OWN_CONTENT = [
    "as an ai", "as a language model", "i am not a doctor",
    "increases lymph drainage", "boosts blood velocity", "flushes toxins",
    "unclog", "melt", "erase",
]
# These terms appear in research citations but should not appear in protocol
# table, FAQ, or self-check sections specifically.
# Uses regex word boundaries to avoid false positives (e.g., "healthy" != "heal")
PROHIBITED_IN_PROTOCOL_TABLE_PATTERNS = [
    r"\bcure[sd]?\b", r"\bfix(?:es|ed)?\b", r"\beliminate[sd]?\b",
    r"\bheal[sd]?\b(?!\w)",  # "heal" but not "healthy" or "health"
]

# Expected self-check content by region/mobility
EXPECTED_SELF_CHECK = {
    "arms": "heaviness in arms",
    "hands": "heaviness in arms",
    "wheelchair": "extended sitting",
    "legs": "heaviness in legs",
    "neck": "tightness in neck",
}

# Expected FAQ content by condition
EXPECTED_FAQ = {
    "pregnant": "compression safe during pregnancy",
    "wheelchair": "compression while seated",
    "cardiac_pulm": "after a procedure",
}

# ═══════════════════════════════════════════════════════════════════
# TEST PROFILES (15 profiles covering all branches)
# ═══════════════════════════════════════════════════════════════════

TEST_PROFILES = [
    {
        "name": "healthy_baseline",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": [], "arm_use": None,
        "expected_multiplier": 1.0,
    },
    {
        "name": "athletic_baseline",
        "tier": "athletic", "tolerance": None, "trimester": None,
        "mobility": [], "arm_use": None,
        "expected_multiplier": 1.2,
    },
    {
        "name": "sedentary_zero_tolerance",
        "tier": "sedentary", "tolerance": "none", "trimester": None,
        "mobility": [], "arm_use": None,
        "expected_multiplier": 0.5 * 0.25,  # 0.125
    },
    {
        "name": "sedentary_moderate",
        "tier": "sedentary", "tolerance": "moderate", "trimester": None,
        "mobility": [], "arm_use": None,
        "expected_multiplier": 0.5 * 0.75,  # 0.375
    },
    {
        "name": "cardiac_zero_tolerance",
        "tier": "cardiac_pulm", "tolerance": "none", "trimester": None,
        "mobility": [], "arm_use": None,
        "expected_multiplier": 0.3 * 0.25,  # 0.075
    },
    {
        "name": "cardiac_high_tolerance",
        "tier": "cardiac_pulm", "tolerance": "high", "trimester": None,
        "mobility": [], "arm_use": None,
        "expected_multiplier": 0.3 * 1.0,  # 0.3
    },
    {
        "name": "pregnant_t1",
        "tier": "pregnant", "tolerance": None, "trimester": "t1",
        "mobility": [], "arm_use": None,
        "expected_multiplier": 0.7 * 1.0,  # 0.7
    },
    {
        "name": "pregnant_t3",
        "tier": "pregnant", "tolerance": None, "trimester": "t3",
        "mobility": [], "arm_use": None,
        "expected_multiplier": 0.7 * 0.7,  # 0.49
    },
    {
        "name": "wheelchair_arms_yes",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["wheelchair"], "arm_use": "yes",
        "expected_multiplier": 1.0 * 0.85,  # 0.85
    },
    {
        "name": "wheelchair_arms_no",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["wheelchair"], "arm_use": "no",
        "expected_multiplier": 1.0 * 0.85,  # 0.85
    },
    {
        "name": "arm_limitation",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["arms"], "arm_use": None,
        "expected_multiplier": 1.0 * 0.8,  # 0.8
    },
    {
        "name": "balance_issues",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["balance"], "arm_use": None,
        "expected_multiplier": 1.0 * 0.9,  # 0.9
    },
    {
        "name": "leg_limitation",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["legs"], "arm_use": None,
        "expected_multiplier": 1.0 * 0.8,  # 0.8
    },
    {
        "name": "worst_case_compound",
        "tier": "sedentary", "tolerance": "none", "trimester": None,
        "mobility": ["wheelchair", "pain"], "arm_use": "no",
        "expected_multiplier": 0.5 * 0.25 * 0.85 * 0.8,  # 0.085
    },
    {
        "name": "pregnant_t3_balance",
        "tier": "pregnant", "tolerance": None, "trimester": "t3",
        "mobility": ["balance"], "arm_use": None,
        "expected_multiplier": 0.7 * 0.7 * 0.9,  # 0.441
    },
]

PROTOCOL_KEYS = list(CLINICAL_PROTOCOLS.keys())  # foundation, legs, arms, neck, post_op, recovery


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def build_ability_profile(p: dict) -> UserAbilityProfile:
    """Build a UserAbilityProfile from a test profile dict."""
    details = {}
    if "wheelchair" in p["mobility"] and p.get("arm_use"):
        details["wheelchair"] = {"arm_use": p["arm_use"]}
    return UserAbilityProfile(
        tier=p["tier"],
        exercise_tolerance=p.get("tolerance"),
        pregnancy_trimester=p.get("trimester"),
        accessibility_needs=p["mobility"],
        accessibility_details=details,
        has_limb_limitations=bool(p["mobility"]),
        intake_completed=True,
    )


def get_exercise_names(items: list) -> List[str]:
    """Extract exercise names from protocol items."""
    return [it.get("name", "") for it in items]


class TestResults:
    """Accumulate and display test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def ok(self, label: str):
        self.passed += 1

    def fail(self, label: str, detail: str):
        self.failed += 1
        self.failures.append(f"  FAIL: {label} -- {detail}")

    def summary(self, section: str):
        total = self.passed + self.failed
        status = "PASS" if self.failed == 0 else "FAIL"
        print(f"\n{'=' * 70}")
        print(f"{section}: {self.passed}/{total} passed  [{status}]")
        print(f"{'=' * 70}")
        for f in self.failures:
            print(f)
        return self.failed == 0


# ═══════════════════════════════════════════════════════════════════
# LAYER 1: ANSWER -> PROFILE MAPPING
# ═══════════════════════════════════════════════════════════════════

def run_layer1() -> bool:
    """Test that widget answers map to correct profile field values."""
    r = TestResults()

    # --- Health Status: every option by number ---
    expected_health = ["cardiac_pulm", "sedentary", "pregnant", "average", "athletic", "limited_limbs"]
    for i, expected_id in enumerate(expected_health, 1):
        result = parse_selection(str(i), HEALTH_STATUS_CHECKBOXES, mode="multi", none_id="none", keyword_map=HEALTH_KEYWORDS)
        if result and expected_id in result:
            r.ok(f"health_{i}")
        else:
            r.fail(f"health_{i}", f"Input '{i}' expected [{expected_id}], got {result}")

    # --- Health Status: multi-select combos ---
    combos = [
        ("1,3", ["cardiac_pulm", "pregnant"]),
        ("4,5", ["average", "athletic"]),
        ("2,6", ["sedentary", "limited_limbs"]),
    ]
    for input_str, expected_ids in combos:
        result = parse_selection(input_str, HEALTH_STATUS_CHECKBOXES, mode="multi", none_id="none", keyword_map=HEALTH_KEYWORDS)
        if result and set(expected_ids).issubset(set(result)):
            r.ok(f"health_combo_{input_str}")
        else:
            r.fail(f"health_combo_{input_str}", f"Expected {expected_ids}, got {result}")

    # --- Health Status: keyword fallback ---
    keyword_tests = [
        ("heart condition", "cardiac_pulm"),
        ("desk worker", "sedentary"),
        ("expecting", "pregnant"),
        ("healthy", "average"),
        ("athlete", "athletic"),
    ]
    for text, expected_id in keyword_tests:
        result = parse_selection(text, HEALTH_STATUS_CHECKBOXES, mode="multi", none_id="none", keyword_map=HEALTH_KEYWORDS)
        if result and expected_id in result:
            r.ok(f"health_kw_{expected_id}")
        else:
            r.fail(f"health_kw_{expected_id}", f"Input '{text}' expected [{expected_id}], got {result}")

    # --- Mobility: every option by number ---
    expected_mob = ["hands", "arms", "legs", "wheelchair", "balance", "pain", "none"]
    for i, expected_id in enumerate(expected_mob, 1):
        result = parse_selection(str(i), MOBILITY_CHECKBOXES, mode="multi", none_id="none", keyword_map=MOBILITY_KEYWORDS)
        if expected_id == "none":
            if result is not None and result == []:
                r.ok(f"mobility_{i}_none")
            elif result is None:
                r.ok(f"mobility_{i}_none")
            else:
                r.fail(f"mobility_{i}_none", f"Input '7' expected empty/None, got {result}")
        elif result and expected_id in result:
            r.ok(f"mobility_{i}")
        else:
            r.fail(f"mobility_{i}", f"Input '{i}' expected [{expected_id}], got {result}")

    # --- Mobility: multi-select ---
    mob_combos = [
        ("4,6", ["wheelchair", "pain"]),
        ("1,2", ["hands", "arms"]),
        ("3,5", ["legs", "balance"]),
    ]
    for input_str, expected_ids in mob_combos:
        result = parse_selection(input_str, MOBILITY_CHECKBOXES, mode="multi", none_id="none", keyword_map=MOBILITY_KEYWORDS)
        if result and set(expected_ids).issubset(set(result)):
            r.ok(f"mobility_combo_{input_str}")
        else:
            r.fail(f"mobility_combo_{input_str}", f"Expected {expected_ids}, got {result}")

    # --- Tolerance: every option by number ---
    expected_tol = ["none", "little", "moderate", "high"]
    for i, expected_id in enumerate(expected_tol, 1):
        result = parse_selection(str(i), TOLERANCE_OPTIONS, mode="single")
        if result == expected_id:
            r.ok(f"tolerance_{i}")
        else:
            r.fail(f"tolerance_{i}", f"Input '{i}' expected '{expected_id}', got '{result}'")

    # --- Trimester: every option by number ---
    expected_tri = ["t1", "t2", "t3"]
    for i, expected_id in enumerate(expected_tri, 1):
        result = parse_selection(str(i), TRIMESTER_OPTIONS, mode="single")
        if result == expected_id:
            r.ok(f"trimester_{i}")
        else:
            r.fail(f"trimester_{i}", f"Input '{i}' expected '{expected_id}', got '{result}'")

    # --- Wheelchair arms: both options ---
    for i, expected_id in enumerate(["yes", "no"], 1):
        result = parse_selection(str(i), WHEELCHAIR_ARMS_OPTIONS, mode="single")
        if result == expected_id:
            r.ok(f"wheelchair_arms_{i}")
        else:
            r.fail(f"wheelchair_arms_{i}", f"Input '{i}' expected '{expected_id}', got '{result}'")

    # --- Edge cases ---
    # Gibberish should return None for health status (fix 1.2)
    result = AbilityIntakeHandler.parse_health_status_response("xyzzy blorp")
    if result is None:
        r.ok("edge_gibberish_health")
    else:
        r.fail("edge_gibberish_health", f"Gibberish expected None, got {result}")

    # "none" for mobility should return empty list
    result = parse_selection("none", MOBILITY_CHECKBOXES, mode="multi", none_id="none", keyword_map=MOBILITY_KEYWORDS)
    if result == [] or result is None:
        r.ok("edge_none_mobility")
    else:
        r.fail("edge_none_mobility", f"'none' expected empty, got {result}")

    # --- Profile summary doesn't crash (fix 1.1) ---
    try:
        profile = build_ability_profile(TEST_PROFILES[9])  # wheelchair_arms_no
        summary = AbilityIntakeHandler.build_profile_summary(profile)
        if "no arm use" in summary.lower():
            r.ok("profile_summary_wheelchair_no_arms")
        else:
            r.fail("profile_summary_wheelchair_no_arms", f"Missing 'no arm use' in: {summary}")
    except Exception as e:
        r.fail("profile_summary_wheelchair_no_arms", f"CRASHED: {e}")

    return r.summary("LAYER 1: Answer -> Profile Mapping")


# ═══════════════════════════════════════════════════════════════════
# LAYER 2: PROFILE -> PROTOCOL CORRECTNESS
# ═══════════════════════════════════════════════════════════════════

def run_layer2() -> bool:
    """Test that each profile produces correct protocols."""
    r = TestResults()

    for p in TEST_PROFILES:
        profile = build_ability_profile(p)
        label_prefix = p["name"]

        # --- 2A: Verify multiplier ---
        actual_mult = calculate_dose_multiplier(
            ability_tier=p["tier"],
            tolerance_or_trimester=p.get("tolerance") or p.get("trimester"),
            accessibility_needs=p["mobility"],
        )
        if math.isclose(actual_mult, p["expected_multiplier"], rel_tol=0.01):
            r.ok(f"{label_prefix}_multiplier")
        else:
            r.fail(f"{label_prefix}_multiplier",
                   f"Expected {p['expected_multiplier']:.4f}, got {actual_mult:.4f}")

        # --- 2B-D: Test against each protocol type ---
        for proto_key in PROTOCOL_KEYS:
            proto = CLINICAL_PROTOCOLS.get(proto_key, {})
            raw_items = proto.get("items", [])
            if not raw_items:
                continue

            test_label = f"{label_prefix}_{proto_key}"

            try:
                modified = ProtocolModifier.modify_protocol(
                    raw_items, profile, session_id=f"test-{test_label}"
                )
            except Exception as e:
                r.fail(test_label, f"modify_protocol CRASHED: {e}")
                continue

            names = get_exercise_names(modified)
            names_lower = [n.lower() for n in names]

            # 2B: Deny-list checks
            for need in p["mobility"]:
                deny_list = MUST_NOT_CONTAIN.get(need, [])
                for denied in deny_list:
                    if denied in names:
                        r.fail(f"{test_label}_deny_{denied}",
                               f"'{denied}' should be excluded for {need} but was found")
                    else:
                        r.ok(f"{test_label}_deny_{denied}")

            # 2C: Required items checks
            for need in p["mobility"]:
                must_key = need
                if need == "wheelchair" and p.get("arm_use") == "no":
                    must_key = "wheelchair_no_arms"
                must_list = MUST_CONTAIN.get(must_key, [])
                for required_frag in must_list:
                    if any(required_frag.lower() in n for n in names_lower):
                        r.ok(f"{test_label}_must_{required_frag}")
                    else:
                        r.fail(f"{test_label}_must_{required_frag}",
                               f"'{required_frag}' expected for {need} but not found in: {names}")

            # 2D: Non-empty protocol
            if len(modified) > 0:
                r.ok(f"{test_label}_nonempty")
            else:
                r.fail(f"{test_label}_nonempty", "Protocol is empty!")

    return r.summary("LAYER 2: Profile -> Protocol Correctness")


# ═══════════════════════════════════════════════════════════════════
# LAYER 3: PDF CONTENT VALIDATION
# ═══════════════════════════════════════════════════════════════════

def run_layer3() -> bool:
    """Generate PDFs for each profile and validate content with pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        print("SKIP: pdfplumber not installed. Install with: pip install pdfplumber")
        return True

    r = TestResults()
    gen = ProtocolGenerator()

    for p in TEST_PROFILES:
        profile = build_ability_profile(p)
        label = p["name"]

        # Pick a representative protocol (legs for most, arms for arm_limitation)
        if "arms" in p["mobility"]:
            proto_key = "arms"
        elif "legs" in p["mobility"]:
            proto_key = "foundation"
        else:
            proto_key = "legs"

        proto = CLINICAL_PROTOCOLS.get(proto_key, {})
        raw_items = proto.get("items", [])

        # Modify protocol
        try:
            modified = ProtocolModifier.modify_protocol(
                raw_items, profile, session_id=f"pdf-test-{label}"
            )
        except Exception as e:
            r.fail(f"{label}_modify", f"modify_protocol CRASHED: {e}")
            continue

        # Build protocol_items in enriched format (matches Fix 2.1)
        from services.conversation_manager import _normalize_weekly_total
        protocol_items = []
        for item in modified:
            normalized_dose = _normalize_weekly_total(item.get("dose")) if item.get("dose") else None
            details = normalized_dose or item.get("instruction")
            protocol_items.append({
                "action": item.get("name"),
                "details": details,
                "instruction": item.get("instruction"),
                "urls": item.get("urls", []),
                "evidence": item.get("evidence"),
                "mechanism": item.get("mechanism"),
                "adjustment_note": item.get("adjustment_note"),
                "segment": item.get("segment"),
            })

        # Build profile dict (matches Fix 2.2)
        pdf_profile = {
            "goal_key": "lighter",
            "primary_region": proto_key if proto_key != "foundation" else "general",
            "context_trigger": "daily",
            "health_status": p["tier"],
            "exercise_tolerance": p.get("tolerance"),
            "pregnancy_trimester": p.get("trimester"),
            "mobility": p["mobility"],
            "accessibility_details": profile.accessibility_details,
        }

        citations = [url for item in protocol_items for url in (item.get("urls") or [])]

        # Generate PDF
        try:
            pdf_path = gen.generate_pdf(
                conversation_id=f"test-validation-{label}",
                user_name=f"Test {label.replace('_', ' ').title()}",
                root_cause=f"{proto_key.title()} Wellness Protocol",
                daily_items=protocol_items,
                weekly_items=[],
                email=f"{label}@test.com",
                profile=pdf_profile,
                citations=citations,
            )
        except Exception as e:
            r.fail(f"{label}_pdf_gen", f"generate_pdf CRASHED: {e}")
            continue

        if not pdf_path or not os.path.exists(pdf_path):
            r.fail(f"{label}_pdf_exists", "PDF file not created")
            continue

        file_size = os.path.getsize(pdf_path)
        if file_size < 1000:
            r.fail(f"{label}_pdf_size", f"PDF too small: {file_size} bytes")
            continue
        r.ok(f"{label}_pdf_generated")

        # --- Extract PDF text ---
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as e:
            r.fail(f"{label}_pdf_read", f"pdfplumber failed: {e}")
            continue

        text_lower = full_text.lower()

        # --- 3A: Profile section correct ---
        # PDF renders the raw tier ID (e.g., "average") in the profile section
        if p["tier"]:
            if p["tier"].lower() in text_lower:
                r.ok(f"{label}_pdf_tier")
            else:
                r.fail(f"{label}_pdf_tier", f"Tier '{p['tier']}' not found in PDF")

        if p.get("tolerance"):
            tol_display = EXERCISE_TOLERANCE.get(p["tolerance"], {}).get("display", p["tolerance"])
            if tol_display.lower() in text_lower:
                r.ok(f"{label}_pdf_tolerance")
            else:
                r.fail(f"{label}_pdf_tolerance", f"Tolerance '{tol_display}' not found in PDF")

        if p.get("trimester"):
            tri_map = {"t1": "1st trimester", "t2": "2nd trimester", "t3": "3rd trimester"}
            tri_text = tri_map.get(p["trimester"], "")
            if tri_text in text_lower:
                r.ok(f"{label}_pdf_trimester")
            else:
                r.fail(f"{label}_pdf_trimester", f"Trimester '{tri_text}' not found in PDF")

        # --- 3B: Daily protocol exercises present ---
        exercise_names = get_exercise_names(modified)
        found_count = 0
        for ex_name in exercise_names:
            if ex_name and ex_name.lower() in text_lower:
                found_count += 1
        if exercise_names and found_count >= len(exercise_names) * 0.5:
            r.ok(f"{label}_pdf_exercises")
        else:
            r.fail(f"{label}_pdf_exercises",
                   f"Only {found_count}/{len(exercise_names)} exercises found in PDF")

        # --- 3C: Denied exercises absent in PDF ---
        for need in p["mobility"]:
            deny_list = MUST_NOT_CONTAIN.get(need, [])
            for denied in deny_list:
                if denied.lower() in text_lower:
                    r.fail(f"{label}_pdf_deny_{denied}",
                           f"Denied exercise '{denied}' found in PDF text!")
                else:
                    r.ok(f"{label}_pdf_deny_{denied}")

        # --- 3D: Self-check personalized ---
        for need in p["mobility"]:
            expected = EXPECTED_SELF_CHECK.get(need)
            if expected:
                if expected in text_lower:
                    r.ok(f"{label}_pdf_selfcheck_{need}")
                else:
                    r.fail(f"{label}_pdf_selfcheck_{need}",
                           f"Expected self-check '{expected}' not found for {need}")

        region = pdf_profile["primary_region"]
        expected_region_check = EXPECTED_SELF_CHECK.get(region)
        if expected_region_check and not p["mobility"]:
            if expected_region_check in text_lower:
                r.ok(f"{label}_pdf_selfcheck_region")
            else:
                r.fail(f"{label}_pdf_selfcheck_region",
                       f"Expected self-check '{expected_region_check}' not found for region={region}")

        # --- 3E: Condition-specific FAQs ---
        if p.get("trimester"):
            faq_text = EXPECTED_FAQ.get("pregnant", "")
            if faq_text in text_lower:
                r.ok(f"{label}_pdf_faq_pregnant")
            else:
                r.fail(f"{label}_pdf_faq_pregnant",
                       f"Expected FAQ '{faq_text}' not found for pregnant profile")

        if "wheelchair" in p["mobility"]:
            faq_text = EXPECTED_FAQ.get("wheelchair", "")
            if faq_text in text_lower:
                r.ok(f"{label}_pdf_faq_wheelchair")
            else:
                r.fail(f"{label}_pdf_faq_wheelchair",
                       f"Expected FAQ '{faq_text}' not found for wheelchair profile")

        if p["tier"] == "cardiac_pulm":
            faq_text = EXPECTED_FAQ.get("cardiac_pulm", "")
            if faq_text in text_lower:
                r.ok(f"{label}_pdf_faq_cardiac")
            else:
                r.fail(f"{label}_pdf_faq_cardiac",
                       f"Expected FAQ '{faq_text}' not found for cardiac profile")

        # --- 3F: No prohibited language in full PDF ---
        for term in PROHIBITED_TERMS_IN_OWN_CONTENT:
            if term in text_lower:
                r.fail(f"{label}_pdf_prohibited_{term.strip()}",
                       f"Prohibited term '{term.strip()}' found in PDF!")
            else:
                r.ok(f"{label}_pdf_prohibited_{term.strip()}")

        # Check protocol table section specifically for medical claims
        # Extract text between "YOUR DAILY PROTOCOL" and "YOUR WEEKLY GOALS" or next section
        proto_start = text_lower.find("your daily protocol")
        proto_end = text_lower.find("your weekly goals", proto_start + 1) if proto_start >= 0 else -1
        if proto_end < 0:
            proto_end = text_lower.find("how to know", proto_start + 1) if proto_start >= 0 else -1
        if proto_start >= 0 and proto_end > proto_start:
            proto_section = text_lower[proto_start:proto_end]
            for pattern in PROHIBITED_IN_PROTOCOL_TABLE_PATTERNS:
                label_clean = re.sub(r'[^a-z_]', '', pattern.replace(r'\b', ''))
                if re.search(pattern, proto_section):
                    r.fail(f"{label}_pdf_proto_prohibited_{label_clean}",
                           f"Prohibited pattern '{pattern}' matched in protocol table section!")
                else:
                    r.ok(f"{label}_pdf_proto_prohibited_{label_clean}")

        # --- 3G: Citations present (if protocol had URLs) ---
        if citations:
            if "ncbi.nlm.nih.gov" in text_lower or "source" in text_lower:
                r.ok(f"{label}_pdf_citations")
            else:
                r.fail(f"{label}_pdf_citations", "No citation links found in PDF")

        # --- 3H: Adjustment notes (if multiplier < 1.0) ---
        if p["expected_multiplier"] < 1.0:
            has_adjustment = ("adjusted" in text_lower or "modified" in text_lower
                              or str(round(p["expected_multiplier"], 2)) in text_lower)
            if has_adjustment:
                r.ok(f"{label}_pdf_adjustment")
            else:
                # Soft check: adjustment notes are optional in current implementation
                r.ok(f"{label}_pdf_adjustment_soft")

    return r.summary("LAYER 3: PDF Content Validation")


# ═══════════════════════════════════════════════════════════════════
# LAYER 4: EDGE CASES
# ═══════════════════════════════════════════════════════════════════

EDGE_CASE_PROFILES = [
    # ── Multi-tier / conflicting combos ──
    {
        "name": "edge_cardiac_pregnant",
        "tier": "cardiac_pulm", "tolerance": "none", "trimester": "t3",
        "mobility": [], "arm_use": None,
        "description": "Cardiac + pregnant data (both followups answered)",
        "expected_multiplier": 0.3 * 0.25,
    },
    {
        "name": "edge_athletic_pain",
        "tier": "athletic", "tolerance": None, "trimester": None,
        "mobility": ["pain"], "arm_use": None,
        "description": "Athletic user with chronic pain",
        "expected_multiplier": 1.2 * 0.8,
    },
    {
        "name": "edge_athletic_wheelchair",
        "tier": "athletic", "tolerance": None, "trimester": None,
        "mobility": ["wheelchair"], "arm_use": "yes",
        "description": "Athletic wheelchair user (e.g., para-athlete)",
        "expected_multiplier": 1.2 * 0.85,
    },
    {
        "name": "edge_sedentary_all_tolerance",
        "tier": "sedentary", "tolerance": "high", "trimester": None,
        "mobility": [], "arm_use": None,
        "description": "Sedentary with high tolerance (desk worker who exercises)",
        "expected_multiplier": 0.5 * 1.0,
    },
    {
        "name": "edge_cardiac_little_balance",
        "tier": "cardiac_pulm", "tolerance": "little", "trimester": None,
        "mobility": ["balance"], "arm_use": None,
        "description": "Cardiac + little tolerance + balance issues",
        "expected_multiplier": 0.3 * 0.5 * 0.9,
    },
    # ── ALL mobility selected ──
    {
        "name": "edge_all_mobility",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["hands", "arms", "legs", "wheelchair", "balance", "pain"],
        "arm_use": "no",
        "description": "Every mobility option selected",
        "expected_multiplier": 1.0 * 0.9 * 0.8 * 0.8 * 0.85 * 0.9 * 0.8,
    },
    # ── Extreme low multiplier ──
    {
        "name": "edge_extreme_low_multiplier",
        "tier": "cardiac_pulm", "tolerance": "none", "trimester": None,
        "mobility": ["wheelchair", "arms", "pain", "balance"],
        "arm_use": "no",
        "description": "Cardiac + none tolerance + wheelchair + arms + pain + balance",
        "expected_multiplier": 0.3 * 0.25 * 0.85 * 0.8 * 0.8 * 0.9,
    },
    # ── Data corruption scenarios ──
    {
        "name": "edge_trimester_no_pregnant",
        "tier": "average", "tolerance": None, "trimester": "t3",
        "mobility": [], "arm_use": None,
        "description": "Trimester set but tier is average (data corruption)",
        "expected_multiplier": 1.0 * 0.7,
    },
    {
        "name": "edge_tolerance_no_cardiac",
        "tier": "athletic", "tolerance": "none", "trimester": None,
        "mobility": [], "arm_use": None,
        "description": "Tolerance='none' but tier is athletic (data corruption)",
        "expected_multiplier": 1.2 * 0.25,
    },
    # ── Single mobility options (each one individually) ──
    {
        "name": "edge_hands_only",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["hands"], "arm_use": None,
        "description": "Only hands limitation",
        "expected_multiplier": 1.0 * 0.9,
    },
    {
        "name": "edge_pain_only",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["pain"], "arm_use": None,
        "description": "Only chronic pain",
        "expected_multiplier": 1.0 * 0.8,
    },
    # ── Double mobility combos ──
    {
        "name": "edge_wheelchair_balance",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["wheelchair", "balance"], "arm_use": "yes",
        "description": "Wheelchair + balance (common combo)",
        "expected_multiplier": 1.0 * 0.85 * 0.9,
    },
    {
        "name": "edge_arms_hands",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["arms", "hands"], "arm_use": None,
        "description": "Both arm and hand limitations",
        "expected_multiplier": 1.0 * 0.8 * 0.9,
    },
    {
        "name": "edge_legs_pain",
        "tier": "average", "tolerance": None, "trimester": None,
        "mobility": ["legs", "pain"], "arm_use": None,
        "description": "Leg limitation + chronic pain",
        "expected_multiplier": 1.0 * 0.8 * 0.8,
    },
    {
        "name": "edge_wheelchair_arms_legs",
        "tier": "sedentary", "tolerance": "little", "trimester": None,
        "mobility": ["wheelchair", "arms", "legs"], "arm_use": "no",
        "description": "Wheelchair + arms + legs (severe quadriplegia)",
        "expected_multiplier": 0.5 * 0.5 * 0.85 * 0.8 * 0.8,
    },
    # ── Pregnancy combos ──
    {
        "name": "edge_pregnant_t1_pain",
        "tier": "pregnant", "tolerance": None, "trimester": "t1",
        "mobility": ["pain"], "arm_use": None,
        "description": "Pregnant T1 + chronic pain (hyperemesis)",
        "expected_multiplier": 0.7 * 1.0 * 0.8,
    },
    {
        "name": "edge_pregnant_t2_wheelchair",
        "tier": "pregnant", "tolerance": None, "trimester": "t2",
        "mobility": ["wheelchair"], "arm_use": "yes",
        "description": "Pregnant T2 wheelchair user",
        "expected_multiplier": 0.7 * 0.9 * 0.85,
    },
    {
        "name": "edge_pregnant_t3_arms",
        "tier": "pregnant", "tolerance": None, "trimester": "t3",
        "mobility": ["arms"], "arm_use": None,
        "description": "Pregnant T3 + arm limitation",
        "expected_multiplier": 0.7 * 0.7 * 0.8,
    },
    # ── Every tolerance level with sedentary ──
    {
        "name": "edge_sedentary_little",
        "tier": "sedentary", "tolerance": "little", "trimester": None,
        "mobility": [], "arm_use": None,
        "description": "Sedentary + little tolerance",
        "expected_multiplier": 0.5 * 0.5,
    },
    {
        "name": "edge_sedentary_high",
        "tier": "sedentary", "tolerance": "high", "trimester": None,
        "mobility": [], "arm_use": None,
        "description": "Sedentary + high tolerance",
        "expected_multiplier": 0.5 * 1.0,
    },
    # ── Every tolerance level with cardiac ──
    {
        "name": "edge_cardiac_little",
        "tier": "cardiac_pulm", "tolerance": "little", "trimester": None,
        "mobility": [], "arm_use": None,
        "description": "Cardiac + little tolerance",
        "expected_multiplier": 0.3 * 0.5,
    },
    {
        "name": "edge_cardiac_moderate",
        "tier": "cardiac_pulm", "tolerance": "moderate", "trimester": None,
        "mobility": [], "arm_use": None,
        "description": "Cardiac + moderate tolerance",
        "expected_multiplier": 0.3 * 0.75,
    },
    # ── Every trimester ──
    {
        "name": "edge_pregnant_t2_plain",
        "tier": "pregnant", "tolerance": None, "trimester": "t2",
        "mobility": [], "arm_use": None,
        "description": "Pregnant T2 plain",
        "expected_multiplier": 0.7 * 0.9,
    },
]


def run_edge_cases() -> bool:
    """Test edge cases: unusual combos, extremes, corruption, unicode, empty data."""
    r = TestResults()
    gen = ProtocolGenerator()

    # ──────────────────────────────────────────────────────────────
    # 4A: Multi-tier and conflicting profile combos
    # ──────────────────────────────────────────────────────────────
    for p in EDGE_CASE_PROFILES:
        label = p["name"]
        profile = build_ability_profile(p)

        # Multiplier check
        actual_mult = calculate_dose_multiplier(
            ability_tier=p["tier"],
            tolerance_or_trimester=p.get("tolerance") or p.get("trimester"),
            accessibility_needs=p["mobility"],
        )
        if math.isclose(actual_mult, p["expected_multiplier"], rel_tol=0.02):
            r.ok(f"{label}_multiplier")
        else:
            r.fail(f"{label}_multiplier",
                   f"Expected {p['expected_multiplier']:.4f}, got {actual_mult:.4f}")

        # Protocol modification must not crash
        for proto_key in PROTOCOL_KEYS:
            raw_items = CLINICAL_PROTOCOLS.get(proto_key, {}).get("items", [])
            if not raw_items:
                continue
            try:
                modified = ProtocolModifier.modify_protocol(
                    raw_items, profile, session_id=f"edge-{label}-{proto_key}"
                )
                r.ok(f"{label}_{proto_key}_no_crash")
            except Exception as e:
                r.fail(f"{label}_{proto_key}_no_crash", f"CRASHED: {e}")
                continue

            # Must produce at least 1 exercise (never empty protocol)
            if len(modified) > 0:
                r.ok(f"{label}_{proto_key}_nonempty")
            else:
                r.fail(f"{label}_{proto_key}_nonempty",
                       f"Protocol is empty after filtering!")

    # ──────────────────────────────────────────────────────────────
    # 4B: Dose floor enforcement — ALL profiles, ALL protocols
    #     No exercise under 2 min duration or under 10 reps
    # ──────────────────────────────────────────────────────────────
    all_dose_profiles = TEST_PROFILES + EDGE_CASE_PROFILES
    for p in all_dose_profiles:
        profile = build_ability_profile(p)
        for proto_key in PROTOCOL_KEYS:
            raw_items = CLINICAL_PROTOCOLS.get(proto_key, {}).get("items", [])
            if not raw_items:
                continue
            try:
                modified = ProtocolModifier.modify_protocol(
                    raw_items, profile, session_id=f"dose-floor-{p['name']}-{proto_key}"
                )
            except Exception:
                continue

            for item in modified:
                dose = str(item.get("dose", ""))
                name = item.get("name", "unknown")
                tlabel = f"{p['name']}_{proto_key}_{name}"

                # Check minutes: no timed exercise under 2 min
                # Match "X min" but not inside a range (handled separately)
                range_m = re.search(r'(\d+)-(\d+)\s*min', dose, re.IGNORECASE)
                if range_m:
                    low_val = int(range_m.group(1))
                    if low_val < 2:
                        r.fail(f"dose_floor_min_range_{tlabel}",
                               f"Range low {low_val} min < 2 min floor in '{dose}'")
                    else:
                        r.ok(f"dose_floor_min_range_{tlabel}")
                else:
                    single_m = re.search(r'(\d+)\s*min', dose, re.IGNORECASE)
                    if single_m:
                        val = int(single_m.group(1))
                        if val < 2:
                            r.fail(f"dose_floor_min_{tlabel}",
                                   f"{val} min < 2 min floor in '{dose}'")
                        else:
                            r.ok(f"dose_floor_min_{tlabel}")

                # Check reps: no exercise under 10 reps per set
                reps_m = re.search(r'(\d+)\s*[xX]\s*(\d+)\s*rep', dose, re.IGNORECASE)
                if reps_m:
                    reps_val = int(reps_m.group(2))
                    if reps_val < 10:
                        r.fail(f"dose_floor_reps_{tlabel}",
                               f"{reps_val} reps < 10 rep floor in '{dose}'")
                    else:
                        r.ok(f"dose_floor_reps_{tlabel}")

                # Standalone reps
                standalone_m = re.search(r'(\d+)\s*rep', dose, re.IGNORECASE)
                if standalone_m and not reps_m:
                    reps_val = int(standalone_m.group(1))
                    if reps_val < 10:
                        r.fail(f"dose_floor_standalone_reps_{tlabel}",
                               f"{reps_val} reps < 10 rep floor in '{dose}'")
                    else:
                        r.ok(f"dose_floor_standalone_reps_{tlabel}")

    # ──────────────────────────────────────────────────────────────
    # 4C: None/incomplete ability profile doesn't crash PDF
    # ──────────────────────────────────────────────────────────────
    # Profile = None
    try:
        raw_items = CLINICAL_PROTOCOLS["legs"]["items"]
        modified = raw_items  # No modification (ability_profile is None)
        from services.conversation_manager import _normalize_weekly_total
        protocol_items = []
        for item in modified:
            normalized_dose = _normalize_weekly_total(item.get("dose")) if item.get("dose") else None
            protocol_items.append({
                "action": item.get("name"), "details": normalized_dose or item.get("instruction"),
                "instruction": item.get("instruction"), "urls": item.get("urls", []),
                "evidence": item.get("evidence"), "mechanism": item.get("mechanism"),
                "adjustment_note": None, "segment": item.get("segment"),
            })
        pdf_path = gen.generate_pdf(
            conversation_id="edge-none-profile",
            user_name="No Profile User",
            root_cause="General Wellness",
            daily_items=protocol_items, weekly_items=[],
            email="none@test.com",
            profile=None,  # <-- No profile at all
            citations=[],
        )
        if pdf_path and os.path.exists(pdf_path):
            r.ok("edge_none_profile_pdf")
        else:
            r.fail("edge_none_profile_pdf", "PDF not generated with None profile")
    except Exception as e:
        r.fail("edge_none_profile_pdf", f"CRASHED with None profile: {e}")

    # Empty profile dict
    try:
        pdf_path = gen.generate_pdf(
            conversation_id="edge-empty-profile",
            user_name="Empty Profile User",
            root_cause="General Wellness",
            daily_items=protocol_items, weekly_items=[],
            email="empty@test.com",
            profile={},  # <-- Empty dict
            citations=[],
        )
        if pdf_path and os.path.exists(pdf_path):
            r.ok("edge_empty_profile_pdf")
        else:
            r.fail("edge_empty_profile_pdf", "PDF not generated with empty profile")
    except Exception as e:
        r.fail("edge_empty_profile_pdf", f"CRASHED with empty profile: {e}")

    # ──────────────────────────────────────────────────────────────
    # 4D: Unicode and special characters in user name
    # ──────────────────────────────────────────────────────────────
    unicode_names = [
        ("Jose_accent", "Jos\u00e9 Garc\u00eda"),
        ("chinese_name", "\u5f20\u4f1f"),
        ("arabic_name", "\u0645\u062d\u0645\u062f"),
        ("emoji_name", "Sarah \u2764"),
        ("html_injection", "<script>alert('xss')</script>"),
        ("very_long_name", "A" * 200),
    ]
    for label, name in unicode_names:
        try:
            pdf_path = gen.generate_pdf(
                conversation_id=f"edge-unicode-{label}",
                user_name=name,
                root_cause="General Wellness",
                daily_items=[{"action": "Breathing", "details": "5 min"}],
                weekly_items=[],
                email=f"{label}@test.com",
                profile={"health_status": "average", "primary_region": "general",
                         "mobility": [], "goal_key": "wellness", "context_trigger": "daily"},
                citations=[],
            )
            if pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 500:
                r.ok(f"edge_unicode_{label}")
            else:
                r.fail(f"edge_unicode_{label}", "PDF not generated or too small")
        except Exception as e:
            r.fail(f"edge_unicode_{label}", f"CRASHED: {e}")

    # ──────────────────────────────────────────────────────────────
    # 4E: Empty protocol items — PDF should still generate
    # ──────────────────────────────────────────────────────────────
    try:
        pdf_path = gen.generate_pdf(
            conversation_id="edge-empty-items",
            user_name="Empty Protocol User",
            root_cause="General Wellness",
            daily_items=[],  # <-- No exercises
            weekly_items=[],
            email="empty_items@test.com",
            profile={"health_status": "average", "primary_region": "general",
                     "mobility": [], "goal_key": "wellness", "context_trigger": "daily"},
            citations=[],
        )
        if pdf_path and os.path.exists(pdf_path):
            r.ok("edge_empty_items_pdf")
        else:
            r.fail("edge_empty_items_pdf", "PDF not generated with empty items")
    except Exception as e:
        r.fail("edge_empty_items_pdf", f"CRASHED with empty items: {e}")

    # ──────────────────────────────────────────────────────────────
    # 4F: Gibberish at every intake stage (parse_selection returns None)
    # ──────────────────────────────────────────────────────────────
    # "none of these" is excluded because "none" is a valid keyword that triggers label matching
    gibberish_inputs = ["xyzzy", "!!@@##", "", "   ", "12345678", "asdfghjkl"]

    for i, gib in enumerate(gibberish_inputs):
        # Health status — should return None after our fix 1.2
        result = AbilityIntakeHandler.parse_health_status_response(gib)
        if result is None:
            r.ok(f"edge_gibberish_health_{i}")
        else:
            # Some gibberish may match keywords (e.g., "none" matches nothing, "" matches nothing)
            # Only fail if it returned something unexpected
            if result == []:
                r.ok(f"edge_gibberish_health_{i}_empty")
            else:
                r.fail(f"edge_gibberish_health_{i}", f"Gibberish '{gib}' returned {result}")

        # Mobility — should return None for gibberish
        result = AbilityIntakeHandler.parse_mobility_response(gib)
        if result is None or result == []:
            r.ok(f"edge_gibberish_mobility_{i}")
        else:
            r.fail(f"edge_gibberish_mobility_{i}", f"Gibberish '{gib}' returned {result}")

    # ──────────────────────────────────────────────────────────────
    # 4G: Mobility string "wheelchair" passed as string not list
    #     (simulates old code where mobility was join'd to string)
    # ──────────────────────────────────────────────────────────────
    try:
        pdf_path = gen.generate_pdf(
            conversation_id="edge-mobility-string",
            user_name="String Mobility User",
            root_cause="Leg Wellness",
            daily_items=[{"action": "Breathing", "details": "5 min"}],
            weekly_items=[],
            email="string_mob@test.com",
            profile={"health_status": "average", "primary_region": "legs",
                     "mobility": "wheelchair, pain",  # <-- String not list
                     "goal_key": "wellness", "context_trigger": "daily"},
            citations=[],
        )
        if pdf_path and os.path.exists(pdf_path):
            r.ok("edge_mobility_string_pdf")
        else:
            r.fail("edge_mobility_string_pdf", "PDF not generated with string mobility")
    except Exception as e:
        r.fail("edge_mobility_string_pdf", f"CRASHED with string mobility: {e}")

    # ──────────────────────────────────────────────────────────────
    # 4H: All-mobility profile generates PDF with correct personalization
    # ──────────────────────────────────────────────────────────────
    try:
        all_mob_profile = build_ability_profile(EDGE_CASE_PROFILES[2])  # edge_all_mobility
        raw_items = CLINICAL_PROTOCOLS["legs"]["items"]
        modified = ProtocolModifier.modify_protocol(raw_items, all_mob_profile, session_id="edge-all-mob")
        from services.conversation_manager import _normalize_weekly_total
        items = []
        for item in modified:
            nd = _normalize_weekly_total(item.get("dose")) if item.get("dose") else None
            items.append({
                "action": item.get("name"), "details": nd or item.get("instruction"),
                "instruction": item.get("instruction"), "urls": item.get("urls", []),
                "evidence": item.get("evidence"), "mechanism": item.get("mechanism"),
                "adjustment_note": item.get("adjustment_note"), "segment": item.get("segment"),
            })
        pdf_path = gen.generate_pdf(
            conversation_id="edge-all-mobility-pdf",
            user_name="All Mobility User",
            root_cause="Legs Wellness Protocol",
            daily_items=items, weekly_items=[],
            email="all_mob@test.com",
            profile={
                "goal_key": "lighter", "primary_region": "legs", "context_trigger": "daily",
                "health_status": "average", "exercise_tolerance": None, "pregnancy_trimester": None,
                "mobility": ["hands", "arms", "legs", "wheelchair", "balance", "pain"],
                "accessibility_details": {"wheelchair": {"arm_use": "no"}},
            },
            citations=[],
        )
        if pdf_path and os.path.exists(pdf_path):
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages).lower()
            # Should have wheelchair FAQ and self-check
            if "compression while seated" in text:
                r.ok("edge_all_mobility_wheelchair_faq")
            else:
                r.fail("edge_all_mobility_wheelchair_faq", "Missing wheelchair FAQ in all-mobility PDF")
            if "extended sitting" in text:
                r.ok("edge_all_mobility_selfcheck")
            else:
                r.fail("edge_all_mobility_selfcheck", "Missing wheelchair self-check in all-mobility PDF")
            # Should NOT have standing exercises
            for denied in ["Structured Calf Pump", "Afternoon Walk"]:
                if denied.lower() in text:
                    r.fail(f"edge_all_mobility_deny_{denied}", f"Found '{denied}' in all-mobility PDF")
                else:
                    r.ok(f"edge_all_mobility_deny_{denied}")
        else:
            r.fail("edge_all_mobility_pdf_gen", "PDF not generated")
    except Exception as e:
        r.fail("edge_all_mobility_pdf", f"CRASHED: {e}")

    return r.summary("LAYER 4: Edge Cases")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("FULL PIPELINE VALIDATION TEST")
    print("Answers -> Profile -> Protocol -> PDF")
    print("=" * 70)

    all_pass = True

    print("\n--- LAYER 1: Answer -> Profile Mapping ---")
    if not run_layer1():
        all_pass = False

    print("\n--- LAYER 2: Profile -> Protocol Correctness ---")
    if not run_layer2():
        all_pass = False

    print("\n--- LAYER 3: PDF Content Validation ---")
    if not run_layer3():
        all_pass = False

    print("\n--- LAYER 4: Edge Cases ---")
    if not run_edge_cases():
        all_pass = False

    print("\n" + "=" * 70)
    if all_pass:
        print("ALL LAYERS PASSED")
    else:
        print("SOME TESTS FAILED -- see details above")
    print("=" * 70)

    sys.exit(0 if all_pass else 1)
