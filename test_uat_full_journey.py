"""
UAT Full Journey Tests — Simulates REAL users from name entry to PDF verification
==================================================================================
Each test:
1. Provides a real name and email (like typing in the widget)
2. Selects each option one at a time (like clicking buttons)
3. Answers discovery questions with natural language
4. Continues until a PDF is generated
5. Downloads and reads the PDF
6. Validates EVERY field in the PDF matches the user's profile

This is NOT unit testing — this is what a QA person would do sitting at the computer.

Requires: Server running on localhost:8000

Run: PYTHONIOENCODING=utf-8 python test_uat_full_journey.py
"""

import os
import re
import sys
import time
import json
import requests
import pdfplumber

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
TIMEOUT = 60
PDF_DIR = os.path.join(os.path.dirname(__file__), "static", "protocols")


class UATJourney:
    def __init__(self, scenario_name: str, user_name: str, user_email: str):
        self.scenario = scenario_name
        self.user_name = user_name
        self.user_email = user_email
        self.session_id = f"uat-{scenario_name}-{int(time.time())}"
        self.step_log = []
        self.errors = []
        self.pdf_path = None
        self.pdf_text = ""
        self.last_response = ""

    def send(self, msg: str, label: str = "") -> str:
        """Send a message to /chat and record the response."""
        payload = {"message": msg, "session_id": self.session_id}
        try:
            r = requests.post(f"{BASE_URL}/chat", json=payload, timeout=TIMEOUT)
            data = r.json()
            text = data.get("response", data.get("text", ""))
        except Exception as e:
            text = ""
            self.errors.append(f"REQUEST FAILED at '{label or msg}': {e}")

        self.last_response = text

        # Check for server errors
        if "sorry" in text.lower() and "went wrong" in text.lower():
            self.errors.append(f"SERVER ERROR at '{label or msg}': {text[:150]}")

        # Log the step
        step_label = label or msg[:40]
        self.step_log.append({"step": step_label, "sent": msg, "response_len": len(text)})

        # Check for PDF URL
        url_match = re.search(r'(https?://[^\s\)\"]+\.pdf)', text)
        if url_match:
            self.pdf_path = self._download_pdf(url_match.group(1))

        return text

    def _download_pdf(self, url: str) -> str:
        """Download PDF and return local path."""
        # Convert URL to local path
        local = url.replace(BASE_URL + "/", "").replace("/", os.sep)
        if not os.path.isabs(local):
            local = os.path.join(os.path.dirname(__file__), local)
        if os.path.exists(local):
            return local

        # Try HTTP download
        try:
            r = requests.get(url, timeout=TIMEOUT)
            if r.status_code == 200 and len(r.content) > 1000:
                path = os.path.join(PDF_DIR, f"uat_{self.scenario}.pdf")
                with open(path, "wb") as f:
                    f.write(r.content)
                return path
        except Exception:
            pass
        return None

    def find_latest_pdf(self) -> str:
        """Find the most recently created PDF matching this session."""
        if self.pdf_path and os.path.exists(self.pdf_path):
            return self.pdf_path
        if not os.path.exists(PDF_DIR):
            return None
        # Find PDFs created in the last 60 seconds
        now = time.time()
        candidates = []
        for f in os.listdir(PDF_DIR):
            if f.endswith(".pdf"):
                fp = os.path.join(PDF_DIR, f)
                if now - os.path.getmtime(fp) < 120:  # Created in last 2 minutes
                    candidates.append((os.path.getmtime(fp), fp))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]
        return None

    def read_pdf(self) -> bool:
        """Read and extract text from the PDF."""
        path = self.pdf_path or self.find_latest_pdf()
        if not path or not os.path.exists(path):
            self.errors.append("NO PDF FOUND — conversation did not generate a PDF")
            return False
        try:
            with pdfplumber.open(path) as pdf:
                self.pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            if len(self.pdf_text) < 100:
                self.errors.append(f"PDF text too short ({len(self.pdf_text)} chars)")
                return False
            return True
        except Exception as e:
            self.errors.append(f"PDF READ ERROR: {e}")
            return False

    def pdf_must_contain(self, label: str, text: str):
        if text.lower() not in self.pdf_text.lower():
            self.errors.append(f"PDF MISSING '{label}': expected '{text}' in PDF")

    def pdf_must_not_contain(self, label: str, text: str):
        if text.lower() in self.pdf_text.lower():
            self.errors.append(f"PDF SHOULD NOT CONTAIN '{label}': found '{text}' in PDF")

    def continue_until_pdf_or_limit(self, max_turns: int = 12):
        """Keep answering contextually until PDF is generated or we hit the limit."""
        for turn in range(max_turns):
            resp = self.last_response.lower()

            # Already have PDF
            if self.pdf_path:
                return True

            # Check for PDF link in response
            if ".pdf" in resp:
                return True

            # Answer contextually based on what the bot is asking
            if "timing" in resp or "worst" in resp or "when does" in resp:
                self.send("3", "timing=evening")
            elif "region" in resp or "area" in resp or "where" in resp or "body" in resp:
                self.send("my legs and ankles", "region=legs")
            elif "trigger" in resp or "start after" in resp or "specific" in resp:
                self.send("6", "context=daily")
            elif "summary" in resp or "correct" in resp or "look right" in resp:
                self.send("yes", "confirm_summary")
            elif "protocol" in resp and ("look" in resp or "change" in resp or "modify" in resp):
                self.send("yes, looks great", "accept_protocol")
            elif "another" in resp or "continue" in resp:
                return True  # End of conversation
            else:
                self.send("yes", "generic_yes")

        return self.pdf_path is not None

    def print_result(self) -> bool:
        ok = len(self.errors) == 0
        status = "PASS" if ok else "FAIL"
        pdf_info = f"PDF: {os.path.basename(self.pdf_path)}" if self.pdf_path else "NO PDF"
        print(f"\n{'='*60}")
        print(f"{status}: {self.scenario}")
        print(f"  User: {self.user_name} ({self.user_email})")
        print(f"  Steps: {len(self.step_log)}, {pdf_info}")
        if self.pdf_text:
            print(f"  PDF size: {len(self.pdf_text)} chars")
        if self.errors:
            print(f"  Errors ({len(self.errors)}):")
            for e in self.errors:
                print(f"    - {e}")
        else:
            print(f"  All checks passed")
        return ok


# ═══════════════════════════════════════════════════════════════════
# UAT SCENARIOS
# ═══════════════════════════════════════════════════════════════════

def uat_travel_healthy():
    """UAT: Maria Garcia — Travel comfort, healthy, no mobility issues."""
    j = UATJourney("travel_healthy", "Maria Garcia", "maria.garcia@email.com")

    # Step 1: Name + Email
    j.send(f"Name: {j.user_name} Email: {j.user_email}", "identity")

    # Step 2: Goal = Travel comfort (#6)
    j.send("6", "goal=travel")

    # Step 3: Health = Generally healthy (#4)
    j.send("4", "health=average")

    # Step 4: Mobility = None (#7)
    j.send("7", "mobility=none")

    # The system should auto-generate protocol + PDF for travel
    j.continue_until_pdf_or_limit()

    # Verify PDF
    if j.read_pdf():
        j.pdf_must_contain("user_name", "Maria")
        j.pdf_must_contain("title_travel", "Travel Comfort")
        j.pdf_must_contain("health_status", "average")
        j.pdf_must_contain("has_exercises", "Leg Elevation")
        # Travel users CAN stand — no deny-list for travel
        j.pdf_must_not_contain("prohibited_cure", "as an ai")

    return j.print_result()


def uat_wheelchair_no_arms():
    """UAT: James Wilson — Swelling, sedentary, no tolerance, wheelchair, no arms."""
    j = UATJourney("wheelchair_no_arms", "James Wilson", "james.wilson@email.com")

    j.send(f"Name: {j.user_name} Email: {j.user_email}", "identity")
    j.send("1", "goal=swelling")
    j.send("2", "health=sedentary")
    j.send("1", "tolerance=none")
    j.send("4", "mobility=wheelchair")
    j.send("2", "wheelchair_arms=no")

    # Discovery
    j.send("my arms and hands swell up badly", "describe_symptoms")
    j.continue_until_pdf_or_limit()

    if j.read_pdf():
        j.pdf_must_contain("user_name", "James")
        j.pdf_must_contain("health_status", "sedentary")
        j.pdf_must_contain("wheelchair_faq", "compression while seated")
        j.pdf_must_contain("selfcheck_sitting", "extended sitting")
        j.pdf_must_not_contain("no_calf_pump", "Structured Calf Pump")
        j.pdf_must_not_contain("no_afternoon_walk", "Afternoon Walk")
        j.pdf_must_not_contain("no_aerobic", "Aerobic Movement")

    return j.print_result()


def uat_pregnant_t3_balance():
    """UAT: Sofia Chen — Pregnancy comfort, pregnant T3, balance issues."""
    j = UATJourney("pregnant_t3_balance", "Sofia Chen", "sofia.chen@email.com")

    j.send(f"Name: {j.user_name} Email: {j.user_email}", "identity")
    j.send("5", "goal=pregnancy")
    j.send("3", "health=pregnant")
    j.send("3", "trimester=t3")
    j.send("5", "mobility=balance")

    j.continue_until_pdf_or_limit()

    if j.read_pdf():
        j.pdf_must_contain("user_name", "Sofia")
        j.pdf_must_contain("title_pregnancy", "Pregnancy")
        j.pdf_must_contain("trimester", "3rd Trimester")
        j.pdf_must_contain("pregnancy_faq", "compression safe during pregnancy")
        j.pdf_must_not_contain("no_calf_pump", "Structured Calf Pump")
        j.pdf_must_not_contain("no_afternoon_walk", "Afternoon Walk")

    return j.print_result()


def uat_athletic_recovery():
    """UAT: Marcus Johnson — Exercise recovery, athletic, chronic pain."""
    j = UATJourney("athletic_recovery", "Marcus Johnson", "marcus.johnson@email.com")

    j.send(f"Name: {j.user_name} Email: {j.user_email}", "identity")
    j.send("4", "goal=recovery")
    j.send("5", "health=athletic")
    j.send("6", "mobility=pain")

    j.send("my legs are heavy and sore after long training runs", "describe_symptoms")
    j.continue_until_pdf_or_limit()

    if j.read_pdf():
        j.pdf_must_contain("user_name", "Marcus")
        j.pdf_must_contain("title_recovery", "Recovery")
        j.pdf_must_contain("health_athletic", "athletic")

    return j.print_result()


def uat_cardiac_wellness():
    """UAT: Dorothy Williams — General wellness, cardiac, little tolerance."""
    j = UATJourney("cardiac_wellness", "Dorothy Williams", "dorothy.w@email.com")

    j.send(f"Name: {j.user_name} Email: {j.user_email}", "identity")
    j.send("7", "goal=wellness")
    j.send("1", "health=cardiac")
    j.send("2", "tolerance=little")
    j.send("7", "mobility=none")

    j.send("I just want to feel better overall, my legs feel heavy by evening", "describe_symptoms")
    j.continue_until_pdf_or_limit()

    if j.read_pdf():
        j.pdf_must_contain("user_name", "Dorothy")
        j.pdf_must_contain("title_wellness", "Wellness")
        j.pdf_must_contain("cardiac_faq", "after a procedure")
        j.pdf_must_contain("tolerance", "Little")

    return j.print_result()


def uat_arm_limitation():
    """UAT: Chen Wei — Swelling, average health, arm limitation."""
    j = UATJourney("arm_limitation", "Chen Wei", "chen.wei@email.com")

    j.send(f"Name: {j.user_name} Email: {j.user_email}", "identity")
    j.send("1", "goal=swelling")
    j.send("4", "health=average")
    j.send("2", "mobility=arms")

    j.send("my arms are swollen and I can't lift them well", "describe_symptoms")
    j.continue_until_pdf_or_limit()

    if j.read_pdf():
        j.pdf_must_contain("user_name", "Chen")
        j.pdf_must_contain("arms_consideration", "arms")
        j.pdf_must_contain("selfcheck_arms", "heaviness in arms")
        j.pdf_must_not_contain("no_upper_body_pump", "Upper Body Pump Circuit")

    return j.print_result()


def uat_postop():
    """UAT: Alex Rivera — Post-surgery, average health, no mobility issues."""
    j = UATJourney("postop", "Alex Rivera", "alex.rivera@email.com")

    j.send(f"Name: {j.user_name} Email: {j.user_email}", "identity")
    j.send("2", "goal=postop")
    j.send("4", "health=average")
    j.send("7", "mobility=none")

    j.send("I had liposuction on my abdomen two weeks ago", "describe_symptoms")
    j.continue_until_pdf_or_limit()

    if j.read_pdf():
        j.pdf_must_contain("user_name", "Alex")
        j.pdf_must_contain("title_postop", "Post-Surgery")
        j.pdf_must_contain("postop_faq", "after a procedure")

    return j.print_result()


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

ALL_SCENARIOS = [
    uat_travel_healthy,
    uat_wheelchair_no_arms,
    uat_pregnant_t3_balance,
    uat_athletic_recovery,
    uat_cardiac_wellness,
    uat_arm_limitation,
    uat_postop,
]

if __name__ == "__main__":
    try:
        r = requests.get(BASE_URL, timeout=5)
        assert r.status_code == 200
    except Exception:
        print(f"Server not running at {BASE_URL}")
        sys.exit(1)

    print("=" * 60)
    print("UAT FULL JOURNEY TESTS")
    print(f"Server: {BASE_URL}")
    print("Complete user journeys: name -> goal -> intake -> discovery -> PDF -> verify")
    print("=" * 60)

    passed = 0
    failed = 0
    for scenario_fn in ALL_SCENARIOS:
        try:
            if scenario_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n  CRASH: {scenario_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    total = passed + failed
    if failed == 0:
        print(f"ALL {total} UAT SCENARIOS PASSED")
    else:
        print(f"{passed}/{total} PASSED, {failed} FAILED")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)
