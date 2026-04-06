"""
Live E2E Flow Tests — POSTs to the actual /chat endpoint
=========================================================
Tests the REAL server routing, state transitions, and responses.
This catches bugs that unit tests miss (variable scoping, stage transitions, etc.)

Requires: Server running on localhost:8000

Run: python test_e2e_live_flows.py
"""

import os
import sys
import time
import json
import requests

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
TIMEOUT = 30

# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

class FlowTest:
    def __init__(self, name: str):
        self.name = name
        self.session_id = f"e2e-{name}-{int(time.time())}"
        self.steps = []
        self.errors = []
        self.last_response = ""

    def chat(self, msg: str, email: str = None) -> str:
        payload = {"message": msg, "session_id": self.session_id}
        if email:
            payload["email"] = email
        try:
            r = requests.post(f"{BASE_URL}/chat", json=payload, timeout=TIMEOUT)
            data = r.json()
            text = data.get("response", data.get("text", ""))
        except Exception as e:
            text = f"[REQUEST FAILED: {e}]"
        self.last_response = text
        self.steps.append({"sent": msg, "got": text[:200]})
        return text

    def expect(self, label: str, *keywords):
        """Check that last_response contains ALL keywords (case-insensitive)."""
        text_lower = self.last_response.lower()
        missing = [kw for kw in keywords if kw.lower() not in text_lower]
        if missing:
            self.errors.append(f"  [{label}] Missing: {missing} in response: {self.last_response[:150]}")
        return len(missing) == 0

    def expect_not(self, label: str, *keywords):
        """Check that last_response does NOT contain any keywords."""
        text_lower = self.last_response.lower()
        found = [kw for kw in keywords if kw.lower() in text_lower]
        if found:
            self.errors.append(f"  [{label}] Should NOT contain: {found}")
        return len(found) == 0

    def expect_no_error(self, label: str):
        """Check response is not an error message."""
        error_phrases = ["sorry", "went wrong", "try again", "error", "traceback"]
        text_lower = self.last_response.lower()
        found = [p for p in error_phrases if p in text_lower]
        if found:
            self.errors.append(f"  [{label}] Got error response containing: {found}")
            return False
        return True

    def result(self) -> bool:
        ok = len(self.errors) == 0
        status = "PASS" if ok else "FAIL"
        print(f"  {status}: {self.name} ({len(self.steps)} steps)")
        for e in self.errors:
            print(e)
        return ok


# ═══════════════════════════════════════════════════════════════════
# FLOW TESTS — Every goal path through the real server
# ═══════════════════════════════════════════════════════════════════

def test_travel_flow():
    """Travel comfort: goal=6 -> health=4(average) -> mobility=7(none) -> discovery"""
    t = FlowTest("travel_comfort")
    t.chat("Name: TravelTest Email: travel@test.com")
    t.expect_no_error("identity")
    t.expect("identity_goal_options", "travel comfort", "what's the main concern")

    t.chat("6")  # Travel comfort
    t.expect_no_error("goal_travel")
    t.expect("goal_travel", "travel comfort", "health")

    t.chat("4")  # Generally healthy
    t.expect_no_error("health")
    t.expect("health_to_mobility", "mobility")

    t.chat("7")  # None
    t.expect_no_error("mobility")
    t.expect("mobility_done", "profile")

    t.chat("my legs swell on long flights")
    t.expect_no_error("discovery_region")

    return t.result()


def test_swelling_flow():
    """Swelling: goal=1 -> health=2(sedentary) -> tolerance=3(moderate) -> mobility=7(none)"""
    t = FlowTest("swelling")
    t.chat("Name: SwellTest Email: swell@test.com")
    t.expect_no_error("identity")

    t.chat("1")  # Swelling
    t.expect_no_error("goal_swelling")
    t.expect("goal_swelling", "swelling", "health")

    t.chat("2")  # Sedentary
    t.expect_no_error("health_sedentary")
    t.expect("health_sedentary", "tolerance")  # Should ask tolerance follow-up

    t.chat("3")  # Moderate
    t.expect_no_error("tolerance")
    t.expect("tolerance_to_mobility", "mobility")

    t.chat("7")  # None
    t.expect_no_error("mobility_done")

    return t.result()


def test_pregnancy_flow():
    """Pregnancy: goal=5 -> health=3(pregnant) -> trimester=3(t3) -> mobility=5(balance)"""
    t = FlowTest("pregnancy")
    t.chat("Name: PregTest Email: preg@test.com")
    t.expect_no_error("identity")

    t.chat("5")  # Pregnancy comfort
    t.expect_no_error("goal_pregnancy")
    t.expect("goal_pregnancy", "pregnancy", "health")

    t.chat("3")  # Pregnant
    t.expect_no_error("health_pregnant")
    t.expect("health_pregnant", "trimester")  # Should ask trimester

    t.chat("3")  # T3
    t.expect_no_error("trimester")
    t.expect("trimester_to_mobility", "mobility")

    t.chat("5")  # Balance
    t.expect_no_error("mobility_balance")

    return t.result()


def test_postop_flow():
    """Post-op: goal=2 -> health=4(average) -> mobility=7(none)"""
    t = FlowTest("postop")
    t.chat("Name: PostOpTest Email: postop@test.com")
    t.expect_no_error("identity")

    t.chat("2")  # Post-surgery
    t.expect_no_error("goal_postop")
    t.expect("goal_postop", "post surgery", "health")

    t.chat("4")  # Average
    t.expect_no_error("health")
    t.expect("health_to_mobility", "mobility")

    t.chat("7")  # None
    t.expect_no_error("mobility_done")

    return t.result()


def test_skin_flow():
    """Skin: goal=3 -> health=5(athletic) -> mobility=7(none)"""
    t = FlowTest("skin")
    t.chat("Name: SkinTest Email: skin@test.com")
    t.expect_no_error("identity")

    t.chat("3")  # Skin
    t.expect_no_error("goal_skin")
    t.expect("goal_skin", "skin", "health")

    t.chat("5")  # Athletic
    t.expect_no_error("health")
    t.expect("health_to_mobility", "mobility")

    t.chat("7")  # None
    t.expect_no_error("mobility_done")

    return t.result()


def test_recovery_flow():
    """Recovery: goal=4 -> health=5(athletic) -> mobility=6(pain)"""
    t = FlowTest("recovery")
    t.chat("Name: RecoveryTest Email: recovery@test.com")
    t.expect_no_error("identity")

    t.chat("4")  # Exercise recovery
    t.expect_no_error("goal_recovery")
    t.expect("goal_recovery", "exercise recovery", "health")

    t.chat("5")  # Athletic
    t.expect_no_error("health")
    t.expect("health_to_mobility", "mobility")

    t.chat("6")  # Pain
    t.expect_no_error("mobility_pain")

    return t.result()


def test_wellness_flow():
    """General wellness: goal=7 -> health=4(average) -> mobility=7(none)"""
    t = FlowTest("general_wellness")
    t.chat("Name: WellnessTest Email: wellness@test.com")
    t.expect_no_error("identity")

    t.chat("7")  # General wellness
    t.expect_no_error("goal_wellness")
    t.expect("goal_wellness", "wellness", "health")

    t.chat("4")  # Average
    t.expect_no_error("health")
    t.expect("health_to_mobility", "mobility")

    t.chat("7")  # None
    t.expect_no_error("mobility_done")

    return t.result()


def test_wheelchair_no_arms_flow():
    """Wheelchair no arms: goal=1 -> health=2(sedentary) -> tolerance=1(none) -> mobility=4(wheelchair) -> arms=2(no)"""
    t = FlowTest("wheelchair_no_arms")
    t.chat("Name: WheelTest Email: wheel@test.com")
    t.expect_no_error("identity")

    t.chat("1")  # Swelling
    t.expect_no_error("goal")
    t.expect("goal", "health")

    t.chat("2")  # Sedentary
    t.expect_no_error("health")
    t.expect("health", "tolerance")

    t.chat("1")  # None tolerance
    t.expect_no_error("tolerance")
    t.expect("tolerance_to_mobility", "mobility")

    t.chat("4")  # Wheelchair
    t.expect_no_error("wheelchair")
    t.expect("wheelchair_arms", "arm")  # Should ask about arm use

    t.chat("2")  # No arm use
    t.expect_no_error("arms_no")

    return t.result()


def test_cardiac_flow():
    """Cardiac: goal=7 -> health=1(cardiac) -> tolerance=2(little) -> mobility=5(balance)"""
    t = FlowTest("cardiac")
    t.chat("Name: CardiacTest Email: cardiac@test.com")
    t.expect_no_error("identity")

    t.chat("7")  # Wellness
    t.expect_no_error("goal")
    t.expect("goal", "health")

    t.chat("1")  # Cardiac
    t.expect_no_error("health")
    t.expect("health_cardiac", "tolerance")

    t.chat("2")  # Little
    t.expect_no_error("tolerance")
    t.expect("tolerance_to_mobility", "mobility")

    t.chat("5")  # Balance
    t.expect_no_error("mobility")

    return t.result()


def test_arm_limitation_flow():
    """Arm limitation: goal=1 -> health=4(average) -> mobility=2(arms)"""
    t = FlowTest("arm_limitation")
    t.chat("Name: ArmTest Email: arm@test.com")
    t.expect_no_error("identity")

    t.chat("1")  # Swelling
    t.expect_no_error("goal")
    t.expect("goal", "health")

    t.chat("4")  # Average
    t.expect_no_error("health")
    t.expect("health_to_mobility", "mobility")

    t.chat("2")  # Arms
    t.expect_no_error("mobility_arms")

    return t.result()


def test_freetext_travel():
    """Free text: user types 'I fly a lot' instead of selecting option 6"""
    t = FlowTest("freetext_travel")
    t.chat("Name: FreeTest Email: free@test.com")
    t.expect_no_error("identity")

    t.chat("I fly a lot and my legs swell on airplanes")
    t.expect_no_error("freetext_travel")
    # Should either get health question or proceed to discovery
    # Key: should NOT loop back to goal selection
    t.expect_not("freetext_no_loop", "what's the main concern")

    return t.result()


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

ALL_TESTS = [
    test_travel_flow,
    test_swelling_flow,
    test_pregnancy_flow,
    test_postop_flow,
    test_skin_flow,
    test_recovery_flow,
    test_wellness_flow,
    test_wheelchair_no_arms_flow,
    test_cardiac_flow,
    test_arm_limitation_flow,
    test_freetext_travel,
]

if __name__ == "__main__":
    # Check server is up
    try:
        r = requests.get(BASE_URL, timeout=5)
        if r.status_code != 200:
            print(f"Server not responding at {BASE_URL}")
            sys.exit(1)
    except Exception:
        print(f"Server not running at {BASE_URL}. Start with: python server.py")
        sys.exit(1)

    print("=" * 60)
    print("LIVE E2E FLOW TESTS")
    print(f"Server: {BASE_URL}")
    print("=" * 60)

    passed = 0
    failed = 0
    for test_fn in ALL_TESTS:
        if test_fn():
            passed += 1
        else:
            failed += 1

    print()
    print("=" * 60)
    total = passed + failed
    if failed == 0:
        print(f"ALL {total} FLOWS PASSED")
    else:
        print(f"{passed}/{total} PASSED, {failed} FAILED")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
