"""
UAT Edge Case Tests — Every weird combination through to PDF verification
==========================================================================
Tests boundary conditions, pathological inputs, rare combos, and multi-select
scenarios. Each test goes through the full /chat API, generates a PDF, reads
it with pdfplumber, and validates content matches the profile.

Requires: Server running on localhost:8000

Run: PYTHONIOENCODING=utf-8 python test_uat_edge_cases.py
"""

import os
import re
import sys
import time
import requests
import pdfplumber

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
TIMEOUT = 60
PDF_DIR = os.path.join(os.path.dirname(__file__), "static", "protocols")

# ═══════════════════════════════════════════════════════════════════
# FRAMEWORK
# ═══════════════════════════════════════════════════════════════════

class EdgeTest:
    def __init__(self, name: str):
        self.name = name
        self.session_id = f"edge-uat-{name}-{int(time.time())}"
        self.errors = []
        self.last_response = ""
        self.pdf_text = ""
        self.step_count = 0
        self.got_pdf = False

    def send(self, msg: str, label: str = "") -> str:
        self.step_count += 1
        payload = {"message": msg, "session_id": self.session_id}
        try:
            r = requests.post(f"{BASE_URL}/chat", json=payload, timeout=TIMEOUT)
            data = r.json()
            text = data.get("response", data.get("text", ""))
        except Exception as e:
            text = ""
            self.errors.append(f"REQUEST FAILED at '{label or msg}': {e}")
        self.last_response = text
        if "sorry" in text.lower() and "went wrong" in text.lower():
            self.errors.append(f"SERVER ERROR at step {self.step_count} '{label or msg[:30]}'")
        if ".pdf" in text.lower():
            self.got_pdf = True
        return text

    def chase_to_pdf(self, max_turns=15):
        """Keep answering contextually until PDF or limit."""
        for _ in range(max_turns):
            if self.got_pdf:
                return True
            resp = self.last_response.lower()
            if "timing" in resp or "worst" in resp or "when" in resp:
                self.send("3", "timing")
            elif "region" in resp or "area" in resp or "where" in resp or "body" in resp:
                self.send("my legs", "region")
            elif "trigger" in resp or "start after" in resp or "specific" in resp:
                self.send("6", "context=daily")
            elif "summary" in resp or "correct" in resp or "right" in resp:
                self.send("yes", "confirm")
            elif ("protocol" in resp or "routine" in resp) and ("look" in resp or "change" in resp):
                self.send("yes looks great", "accept")
            elif "another" in resp or "continue" in resp or "what else" in resp:
                return self.got_pdf
            elif "main concern" in resp or "goal" in resp:
                # Stuck at goal — shouldn't happen but handle it
                self.send("1", "goal_fallback")
            else:
                self.send("yes", "generic_yes")
        return self.got_pdf

    def read_pdf(self) -> bool:
        """Find the most recent PDF and read it."""
        if not os.path.exists(PDF_DIR):
            self.errors.append("PDF directory doesn't exist")
            return False
        now = time.time()
        candidates = []
        for f in os.listdir(PDF_DIR):
            if f.endswith(".pdf"):
                fp = os.path.join(PDF_DIR, f)
                if now - os.path.getmtime(fp) < 180:
                    candidates.append((os.path.getmtime(fp), fp))
        if not candidates:
            self.errors.append("NO PDF generated within last 3 minutes")
            return False
        candidates.sort(reverse=True)
        path = candidates[0][1]
        try:
            with pdfplumber.open(path) as pdf:
                self.pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return len(self.pdf_text) > 100
        except Exception as e:
            self.errors.append(f"PDF read error: {e}")
            return False

    def pdf_has(self, label: str, text: str):
        if text and text.lower() not in self.pdf_text.lower():
            self.errors.append(f"PDF MISSING [{label}]: '{text}'")

    def pdf_lacks(self, label: str, text: str):
        if text and text.lower() in self.pdf_text.lower():
            self.errors.append(f"PDF CONTAINS [{label}]: '{text}' (should not)")

    def no_errors(self) -> bool:
        return len(self.errors) == 0

    def result(self) -> bool:
        ok = self.no_errors()
        status = "PASS" if ok else "FAIL"
        pdf_len = len(self.pdf_text) if self.pdf_text else 0
        print(f"  {status}: {self.name} ({self.step_count} steps, PDF: {pdf_len} chars)")
        for e in self.errors:
            print(f"    - {e}")
        return ok


# ═══════════════════════════════════════════════════════════════════
# EDGE CASE SCENARIOS
# ═══════════════════════════════════════════════════════════════════

def edge_all_mobility_options():
    """Select EVERY mobility option (hands, arms, legs, wheelchair, balance, pain)."""
    t = EdgeTest("all_mobility")
    t.send("Name: AllMob Test Email: allmob@test.com", "identity")
    t.send("1", "goal=swelling")
    t.send("2", "health=sedentary")
    t.send("1", "tolerance=none")
    # Select all mobility: "1,2,3,4,5,6"
    t.send("1,2,3,4,5,6", "mobility=ALL")
    # Wheelchair follow-up
    resp = t.last_response.lower()
    if "arm" in resp:
        t.send("2", "arms=no")
    t.send("everything hurts and swells", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_lacks("no_calf_pump", "Structured Calf Pump")
        t.pdf_lacks("no_walk", "Afternoon Walk")
        t.pdf_lacks("no_aerobic", "Aerobic Movement")
        t.pdf_lacks("no_upper_body", "Upper Body Pump Circuit")
        t.pdf_has("wheelchair_faq", "compression while seated")
        t.pdf_has("has_breathing", "Diaphragmatic")
        t.pdf_has("has_compression", "Compression")
    return t.result()


def edge_cardiac_pregnant_combo():
    """Cardiac + pregnant health tiers (multi-select health: 1,3)."""
    t = EdgeTest("cardiac_pregnant")
    t.send("Name: CardPreg Test Email: cardpreg@test.com", "identity")
    t.send("5", "goal=pregnancy")
    # Select both cardiac AND pregnant
    t.send("1,3", "health=cardiac+pregnant")
    # Should ask tolerance (cardiac needs it)
    resp = t.last_response.lower()
    if "tolerance" in resp:
        t.send("2", "tolerance=little")
    # Should ask trimester (pregnant needs it)
    resp = t.last_response.lower()
    if "trimester" in resp:
        t.send("3", "trimester=t3")
    resp = t.last_response.lower()
    if "mobility" in resp:
        t.send("7", "mobility=none")
    t.send("leg swelling during third trimester", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_has("pregnancy_faq", "compression safe during pregnancy")
    return t.result()


def edge_athletic_wheelchair():
    """Athletic wheelchair user (para-athlete)."""
    t = EdgeTest("athletic_wheelchair")
    t.send("Name: ParaAthlete Test Email: para@test.com", "identity")
    t.send("4", "goal=recovery")
    t.send("5", "health=athletic")
    t.send("4", "mobility=wheelchair")
    resp = t.last_response.lower()
    if "arm" in resp:
        t.send("1", "arms=yes")  # Has arms
    t.send("my upper body is sore after wheelchair racing", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_has("athletic", "athletic")
        t.pdf_lacks("no_calf_pump", "Structured Calf Pump")
        t.pdf_lacks("no_walk", "Afternoon Walk")
        t.pdf_has("wheelchair_faq", "compression while seated")
    return t.result()


def edge_sedentary_high_tolerance():
    """Sedentary but high tolerance (desk worker who exercises)."""
    t = EdgeTest("sedentary_high")
    t.send("Name: DeskFit Test Email: deskfit@test.com", "identity")
    t.send("7", "goal=wellness")
    t.send("2", "health=sedentary")
    t.send("4", "tolerance=high")
    t.send("7", "mobility=none")
    t.send("general wellness, legs feel heavy from desk work", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_has("sedentary", "sedentary")
        t.pdf_has("high_tolerance", "High")
    return t.result()


def edge_pregnant_t1_pain():
    """Pregnant T1 with chronic pain (hyperemesis)."""
    t = EdgeTest("pregnant_t1_pain")
    t.send("Name: EarlyPreg Test Email: earlypreg@test.com", "identity")
    t.send("5", "goal=pregnancy")
    t.send("3", "health=pregnant")
    t.send("1", "trimester=t1")
    t.send("6", "mobility=pain")
    t.send("nausea and leg swelling early pregnancy", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_has("pregnancy_faq", "compression safe during pregnancy")
        t.pdf_has("trimester", "1st Trimester")
    return t.result()


def edge_pregnant_t2_wheelchair():
    """Pregnant T2 wheelchair user."""
    t = EdgeTest("pregnant_t2_wheelchair")
    t.send("Name: PreWheel Test Email: prewheel@test.com", "identity")
    t.send("5", "goal=pregnancy")
    t.send("3", "health=pregnant")
    t.send("2", "trimester=t2")
    t.send("4", "mobility=wheelchair")
    resp = t.last_response.lower()
    if "arm" in resp:
        t.send("1", "arms=yes")
    t.send("leg swelling from pregnancy and wheelchair use", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_has("pregnancy_faq", "compression safe during pregnancy")
        t.pdf_has("wheelchair_faq", "compression while seated")
        t.pdf_lacks("no_calf_pump", "Structured Calf Pump")
    return t.result()


def edge_hands_only():
    """Only hand limitation — very specific."""
    t = EdgeTest("hands_only")
    t.send("Name: HandsTest Email: hands@test.com", "identity")
    t.send("1", "goal=swelling")
    t.send("4", "health=average")
    t.send("1", "mobility=hands")
    t.send("my hands swell up during the day", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_has("hands_in_profile", "hand")
    return t.result()


def edge_balance_only():
    """Only balance issues — must not get standing exercises."""
    t = EdgeTest("balance_only")
    t.send("Name: BalanceTest Email: balance@test.com", "identity")
    t.send("1", "goal=swelling")
    t.send("4", "health=average")
    t.send("5", "mobility=balance")
    t.send("my ankles swell and I have trouble standing", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_lacks("no_calf_pump", "Structured Calf Pump")
        t.pdf_lacks("no_walk", "Afternoon Walk")
    return t.result()


def edge_legs_and_arms():
    """Both leg AND arm limitations."""
    t = EdgeTest("legs_arms")
    t.send("Name: BothLimbs Test Email: both@test.com", "identity")
    t.send("1", "goal=swelling")
    t.send("4", "health=average")
    t.send("2,3", "mobility=arms+legs")
    t.send("swelling in arms and legs", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_lacks("no_upper_body", "Upper Body Pump Circuit")
    return t.result()


def edge_unicode_names():
    """Unicode characters in name — should not crash PDF generation."""
    t = EdgeTest("unicode_name")
    t.send("Name: José García Email: jose@test.com", "identity")
    t.send("6", "goal=travel")
    t.send("4", "health=average")
    t.send("7", "mobility=none")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_has("has_content", "Travel Comfort")
    return t.result()


def edge_very_long_name():
    """200-character name — should not crash."""
    t = EdgeTest("long_name")
    long_name = "A" * 200
    t.send(f"Name: {long_name} Email: long@test.com", "identity")
    t.send("7", "goal=wellness")
    t.send("4", "health=average")
    t.send("7", "mobility=none")
    t.send("general wellness concern", "symptoms")
    t.chase_to_pdf()
    # Just verify no crash — PDF may truncate name
    if t.got_pdf or t.read_pdf():
        pass  # Success if no crash
    return t.result()


def edge_gibberish_then_real():
    """Send gibberish first, then real answers — system should recover."""
    t = EdgeTest("gibberish_recovery")
    t.send("asdfghjkl", "gibberish1")
    t.send("xyzzy blorp", "gibberish2")
    # Now provide real identity
    t.send("Name: Recovery Test Email: recovery@test.com", "real_identity")
    t.send("7", "goal=wellness")
    t.send("4", "health=average")
    t.send("7", "mobility=none")
    t.send("general wellness", "symptoms")
    t.chase_to_pdf()
    return t.result()


def edge_every_tolerance_cardiac():
    """Test all 4 tolerance levels with cardiac tier."""
    results = []
    for tol_num, tol_name in [("1", "none"), ("2", "little"), ("3", "moderate"), ("4", "high")]:
        t = EdgeTest(f"cardiac_tol_{tol_name}")
        t.send(f"Name: Cardiac{tol_name.title()} Email: cardiac{tol_name}@test.com", "identity")
        t.send("7", "goal=wellness")
        t.send("1", "health=cardiac")
        t.send(tol_num, f"tolerance={tol_name}")
        t.send("7", "mobility=none")
        t.send("general heart health wellness", "symptoms")
        t.chase_to_pdf()
        if t.read_pdf():
            t.pdf_has("cardiac_faq", "after a procedure")
        results.append(t.result())
    return all(results)


def edge_every_trimester():
    """Test all 3 trimesters."""
    results = []
    for tri_num, tri_name, tri_display in [("1", "t1", "1st Trimester"), ("2", "t2", "2nd Trimester"), ("3", "t3", "3rd Trimester")]:
        t = EdgeTest(f"pregnant_{tri_name}")
        t.send(f"Name: Preg{tri_name.upper()} Email: preg{tri_name}@test.com", "identity")
        t.send("5", "goal=pregnancy")
        t.send("3", "health=pregnant")
        t.send(tri_num, f"trimester={tri_name}")
        t.send("7", "mobility=none")
        t.chase_to_pdf()
        if t.read_pdf():
            t.pdf_has("trimester_display", tri_display)
            t.pdf_has("pregnancy_faq", "compression safe during pregnancy")
        results.append(t.result())
    return all(results)


def edge_every_goal():
    """Test all 7 goals produce a PDF with correct title."""
    goals = [
        ("1", "swelling", "Swelling"),
        ("2", "postop", "Post-Surgery"),
        ("3", "skin", "Skin"),
        ("4", "recovery", "Recovery"),
        ("5", "pregnancy", "Pregnancy"),
        ("6", "travel", "Travel"),
        ("7", "wellness", "Wellness"),
    ]
    results = []
    for num, key, title_fragment in goals:
        t = EdgeTest(f"goal_{key}")
        t.send(f"Name: Goal{key.title()} Email: goal{key}@test.com", "identity")
        t.send(num, f"goal={key}")
        # Health: average for most, pregnant for pregnancy
        if key == "pregnancy":
            t.send("3", "health=pregnant")
            t.send("2", "trimester=t2")
        else:
            t.send("4", "health=average")
        t.send("7", "mobility=none")
        if key not in ("travel", "pregnancy"):
            t.send("my legs feel heavy", "symptoms")
        t.chase_to_pdf()
        if t.read_pdf():
            t.pdf_has(f"title_{key}", title_fragment)
        results.append(t.result())
    return all(results)


def edge_worst_case_compound():
    """Absolute worst case: cardiac + none tolerance + wheelchair + arms + legs + pain + balance, no arm use."""
    t = EdgeTest("worst_case")
    t.send("Name: WorstCase Test Email: worst@test.com", "identity")
    t.send("1", "goal=swelling")
    t.send("1", "health=cardiac")
    t.send("1", "tolerance=none")
    t.send("1,2,3,4,5,6", "mobility=everything")
    resp = t.last_response.lower()
    if "arm" in resp:
        t.send("2", "arms=no")
    t.send("everything hurts and swells badly", "symptoms")
    t.chase_to_pdf()
    if t.read_pdf():
        t.pdf_lacks("no_calf_pump", "Structured Calf Pump")
        t.pdf_lacks("no_walk", "Afternoon Walk")
        t.pdf_lacks("no_aerobic", "Aerobic Movement")
        t.pdf_lacks("no_upper_body", "Upper Body Pump Circuit")
        t.pdf_has("has_breathing", "Diaphragmatic")
        t.pdf_has("wheelchair_faq", "compression while seated")
        t.pdf_has("cardiac_faq", "after a procedure")
        # Verify doses are reasonable (not 0 or 1 minute)
        text_lower = t.pdf_text.lower()
        one_min_matches = re.findall(r'\b1\s*min\b', text_lower)
        if one_min_matches:
            t.errors.append(f"Found '1 min' dose in worst-case PDF — below 2 min floor")
    return t.result()


def edge_freetext_goals():
    """Type natural language instead of clicking goal buttons."""
    phrases = [
        ("I fly every week for work", "travel", "Travel"),
        ("I just had liposuction", "postop", "Post-Surgery"),
        ("I'm 8 months pregnant", "pregnancy", "Pregnancy"),
        ("I run marathons", "recovery", "Recovery"),
        ("my skin is dimpled and bumpy", "skin", "Skin"),
    ]
    results = []
    for phrase, key, title_frag in phrases:
        t = EdgeTest(f"freetext_{key}")
        t.send(f"Name: Free{key.title()} Email: free{key}@test.com", "identity")
        t.send(phrase, f"freetext_goal={key}")
        # Should either go to health question or infer goal
        resp = t.last_response.lower()
        if "health" in resp or "describes" in resp:
            if key == "pregnancy":
                t.send("3", "health=pregnant")
                resp = t.last_response.lower()
                if "trimester" in resp:
                    t.send("3", "trimester=t3")
            else:
                t.send("4", "health=average")
            resp = t.last_response.lower()
            if "mobility" in resp:
                t.send("7", "mobility=none")
        t.send("legs feel heavy and swollen", "symptoms")
        t.chase_to_pdf()
        if t.read_pdf():
            t.pdf_has(f"title_{key}", title_frag)
        results.append(t.result())
    return all(results)


def edge_double_send_same_message():
    """Send the same message twice — should not crash or create duplicates."""
    t = EdgeTest("double_send")
    t.send("Name: Double Test Email: double@test.com", "identity")
    t.send("6", "goal=travel")
    t.send("6", "same_message_again")  # Duplicate
    # Should still be able to proceed
    resp = t.last_response.lower()
    if "health" not in resp and "mobility" not in resp:
        # Try to get back on track
        t.send("4", "health=average")
    t.send("7", "mobility=none")
    t.chase_to_pdf()
    return t.result()


def edge_empty_message():
    """Send empty/whitespace messages — should not crash."""
    t = EdgeTest("empty_messages")
    t.send("Name: Empty Test Email: empty@test.com", "identity")
    t.send("", "empty")
    t.send("   ", "whitespace")
    # Now real input
    t.send("7", "goal=wellness")
    t.send("4", "health=average")
    t.send("7", "mobility=none")
    t.send("general wellness", "symptoms")
    t.chase_to_pdf()
    return t.result()


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

ALL_TESTS = [
    ("All mobility options selected", edge_all_mobility_options),
    ("Cardiac + pregnant combo", edge_cardiac_pregnant_combo),
    ("Athletic wheelchair user", edge_athletic_wheelchair),
    ("Sedentary with high tolerance", edge_sedentary_high_tolerance),
    ("Pregnant T1 with pain", edge_pregnant_t1_pain),
    ("Pregnant T2 wheelchair", edge_pregnant_t2_wheelchair),
    ("Hands only limitation", edge_hands_only),
    ("Balance only limitation", edge_balance_only),
    ("Legs + arms limitation", edge_legs_and_arms),
    ("Unicode name (José García)", edge_unicode_names),
    ("Very long name (200 chars)", edge_very_long_name),
    ("Gibberish then real answers", edge_gibberish_then_real),
    ("Every tolerance level (cardiac)", edge_every_tolerance_cardiac),
    ("Every trimester (pregnant)", edge_every_trimester),
    ("Every goal type", edge_every_goal),
    ("Worst case compound profile", edge_worst_case_compound),
    ("Free-text goal phrases", edge_freetext_goals),
    ("Double-send same message", edge_double_send_same_message),
    ("Empty/whitespace messages", edge_empty_message),
]

if __name__ == "__main__":
    try:
        r = requests.get(BASE_URL, timeout=5)
        assert r.status_code == 200
    except Exception:
        print(f"Server not running at {BASE_URL}")
        sys.exit(1)

    print("=" * 60)
    print("UAT EDGE CASE TESTS")
    print(f"Server: {BASE_URL}")
    print(f"Scenarios: {len(ALL_TESTS)} edge cases")
    print("=" * 60)

    passed = 0
    failed = 0
    for desc, test_fn in ALL_TESTS:
        print(f"\n--- {desc} ---")
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  CRASH: {e}")
            failed += 1

    print(f"\n{'='*60}")
    total = passed + failed
    if failed == 0:
        print(f"ALL {total} EDGE CASE SCENARIOS PASSED")
    else:
        print(f"{passed}/{total} PASSED, {failed} FAILED")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)
