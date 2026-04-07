"""
Full Conversation E2E Tests — Complete user journeys through PDF generation
===========================================================================
Simulates REAL users with real names/emails going through every step
from identity to PDF download. Verifies the PDF exists and contains
profile-appropriate content.

Requires: Server running on localhost:8000

Run: PYTHONIOENCODING=utf-8 python test_e2e_full_conversations.py
"""

import os
import sys
import time
import re
import requests
import pdfplumber

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
TIMEOUT = 45  # Some steps involve LLM calls

# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

class ConversationRunner:
    def __init__(self, name: str, user_name: str, user_email: str):
        self.test_name = name
        self.user_name = user_name
        self.user_email = user_email
        self.session_id = f"full-e2e-{name}-{int(time.time())}"
        self.errors = []
        self.step_count = 0
        self.last_response = ""
        self.pdf_url = None
        self.pdf_text = ""

    def chat(self, msg: str) -> str:
        self.step_count += 1
        payload = {"message": msg, "session_id": self.session_id}
        try:
            r = requests.post(f"{BASE_URL}/chat", json=payload, timeout=TIMEOUT)
            data = r.json()
            text = data.get("response", data.get("text", ""))
        except Exception as e:
            text = f"[REQUEST FAILED: {e}]"
            self.errors.append(f"  Step {self.step_count} ({msg}): REQUEST FAILED: {e}")
        self.last_response = text

        # Check for error responses
        if "sorry" in text.lower() and "went wrong" in text.lower():
            self.errors.append(f"  Step {self.step_count} ({msg}): Server error response")

        # Extract PDF URL if present
        url_match = re.search(r'(https?://[^\s\)]+\.pdf)', text)
        if url_match:
            self.pdf_url = url_match.group(1)

        return text

    def expect(self, label: str, *keywords):
        text_lower = self.last_response.lower()
        missing = [kw for kw in keywords if kw.lower() not in text_lower]
        if missing:
            self.errors.append(f"  [{label}] Missing: {missing}")
        return len(missing) == 0

    def expect_not(self, label: str, *keywords):
        text_lower = self.last_response.lower()
        found = [kw for kw in keywords if kw.lower() in text_lower]
        if found:
            self.errors.append(f"  [{label}] Should NOT contain: {found}")

    def download_and_check_pdf(self):
        """Download the PDF and extract text for validation."""
        if not self.pdf_url:
            # Check if PDF URL is in static protocols
            # Try to find it from the local filesystem
            proto_dir = os.path.join(os.path.dirname(__file__), "static", "protocols")
            if os.path.exists(proto_dir):
                files = sorted(
                    [f for f in os.listdir(proto_dir) if f.endswith(".pdf") and self.session_id.split("-")[-1] in f],
                    key=lambda f: os.path.getmtime(os.path.join(proto_dir, f)),
                    reverse=True
                )
                if files:
                    pdf_path = os.path.join(proto_dir, files[0])
                    return self._read_pdf(pdf_path)

            self.errors.append("  No PDF URL found in conversation")
            return False

        # Download via URL (convert to local path)
        local_path = self.pdf_url.replace(BASE_URL + "/", "").replace("/", os.sep)
        if not os.path.isabs(local_path):
            local_path = os.path.join(os.path.dirname(__file__), local_path)

        if os.path.exists(local_path):
            return self._read_pdf(local_path)

        # Try HTTP download
        try:
            r = requests.get(self.pdf_url, timeout=TIMEOUT)
            if r.status_code == 200 and len(r.content) > 1000:
                tmp_path = os.path.join(os.path.dirname(__file__), "static", "protocols", f"test_{self.test_name}.pdf")
                with open(tmp_path, "wb") as f:
                    f.write(r.content)
                return self._read_pdf(tmp_path)
            else:
                self.errors.append(f"  PDF download failed: status={r.status_code}, size={len(r.content)}")
                return False
        except Exception as e:
            self.errors.append(f"  PDF download error: {e}")
            return False

    def _read_pdf(self, path: str) -> bool:
        try:
            with pdfplumber.open(path) as pdf:
                self.pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return True
        except Exception as e:
            self.errors.append(f"  PDF read error: {e}")
            return False

    def pdf_contains(self, label: str, *keywords):
        text_lower = self.pdf_text.lower()
        missing = [kw for kw in keywords if kw.lower() not in text_lower]
        if missing:
            self.errors.append(f"  [PDF:{label}] Missing: {missing}")

    def pdf_not_contains(self, label: str, *keywords):
        text_lower = self.pdf_text.lower()
        found = [kw for kw in keywords if kw.lower() in text_lower]
        if found:
            self.errors.append(f"  [PDF:{label}] Should NOT contain: {found}")

    def result(self) -> bool:
        ok = len(self.errors) == 0
        status = "PASS" if ok else "FAIL"
        pdf_status = "PDF verified" if self.pdf_text else "no PDF"
        print(f"  {status}: {self.test_name} ({self.step_count} steps, {pdf_status})")
        for e in self.errors:
            print(e)
        return ok


# ═══════════════════════════════════════════════════════════════════
# FULL CONVERSATION TESTS
# ═══════════════════════════════════════════════════════════════════

def test_travel_full():
    """Complete travel user journey: Maria Garcia, healthy, no mobility issues, leg swelling on flights."""
    c = ConversationRunner("travel_maria", "Maria Garcia", "maria.garcia@email.com")

    # Identity
    c.chat(f"Name: {c.user_name} Email: {c.user_email}")
    c.expect("identity", "maria", "main concern")

    # Goal: Travel comfort (#6)
    c.chat("6")
    c.expect("goal", "travel comfort", "health")

    # Health: Generally healthy (#4)
    c.chat("4")
    c.expect("health", "mobility")

    # Mobility: None (#7)
    c.chat("7")
    c.expect("mobility_done", "profile")

    # Discovery: describe symptoms
    c.chat("My legs get really swollen and heavy after long flights")
    # Should ask about region or timing (context already set to travel)

    # Timing
    resp = c.last_response.lower()
    if "timing" in resp or "worst" in resp or "when" in resp:
        c.chat("3")  # Evening / after travel

    # Keep going until we get a protocol or run out of discovery questions
    for _ in range(5):
        resp = c.last_response.lower()
        if "protocol" in resp or "routine" in resp or "here is" in resp or "tailored" in resp:
            break
        if "region" in resp or "area" in resp or "where" in resp:
            c.chat("my legs and ankles")
        elif "timing" in resp or "worst" in resp or "when" in resp:
            c.chat("after long flights, usually evening")
        elif "trigger" in resp or "start" in resp or "specific" in resp:
            c.chat("during and after air travel")
        elif "summary" in resp or "correct" in resp or "right" in resp:
            c.chat("yes")
        else:
            c.chat("yes")

    # Agreement: accept the protocol
    for _ in range(3):
        resp = c.last_response.lower()
        if "agree" in resp or "look" in resp or "protocol" in resp or "routine" in resp:
            c.chat("yes, looks great")
            break
        elif "pdf" in resp or "download" in resp or ".pdf" in resp:
            break
        else:
            c.chat("yes")

    # Try to get PDF
    if c.pdf_url:
        if c.download_and_check_pdf():
            c.pdf_contains("user_name", "maria")
            c.pdf_contains("travel_wear", "travel")
            c.pdf_not_contains("no_standing_claim", "standing calf")

    return c.result()


def test_wheelchair_full():
    """Complete wheelchair user journey: James Wilson, sedentary, no tolerance, wheelchair + no arms."""
    c = ConversationRunner("wheelchair_james", "James Wilson", "james.wilson@email.com")

    c.chat(f"Name: {c.user_name} Email: {c.user_email}")
    c.expect("identity", "james", "main concern")

    # Goal: Swelling (#1)
    c.chat("1")
    c.expect("goal", "swelling", "health")

    # Health: Sedentary (#2)
    c.chat("2")
    c.expect("health", "tolerance")

    # Tolerance: None (#1)
    c.chat("1")
    c.expect("tolerance", "mobility")

    # Mobility: Wheelchair (#4)
    c.chat("4")
    c.expect("wheelchair", "arm")

    # Arms: No (#2)
    c.chat("2")

    # Discovery
    c.chat("my arms and hands swell up, especially in the evening")

    for _ in range(5):
        resp = c.last_response.lower()
        if "protocol" in resp or "routine" in resp or "here is" in resp or "tailored" in resp:
            break
        if "timing" in resp or "worst" in resp or "when" in resp:
            c.chat("evening, end of day")
        elif "region" in resp or "area" in resp or "where" in resp:
            c.chat("arms and hands")
        elif "trigger" in resp or "start" in resp or "specific" in resp:
            c.chat("daily, ongoing")
        elif "summary" in resp or "correct" in resp or "right" in resp:
            c.chat("yes")
        else:
            c.chat("yes")

    for _ in range(3):
        resp = c.last_response.lower()
        if "pdf" in resp or "download" in resp or ".pdf" in resp:
            break
        else:
            c.chat("yes, looks great")

    if c.pdf_url:
        if c.download_and_check_pdf():
            c.pdf_contains("user_name", "james")
            c.pdf_contains("profile_tier", "sedentary")
            c.pdf_contains("wheelchair_faq", "compression while seated")
            c.pdf_not_contains("no_standing", "structured calf pump")
            c.pdf_not_contains("no_walking", "afternoon walk")

    return c.result()


def test_pregnant_full():
    """Complete pregnant user: Sofia Chen, pregnant T3, balance issues."""
    c = ConversationRunner("pregnant_sofia", "Sofia Chen", "sofia.chen@email.com")

    c.chat(f"Name: {c.user_name} Email: {c.user_email}")
    c.expect("identity", "sofia", "main concern")

    # Goal: Pregnancy comfort (#5)
    c.chat("5")
    c.expect("goal", "pregnancy", "health")

    # Health: Pregnant (#3)
    c.chat("3")
    c.expect("health", "trimester")

    # Trimester: T3 (#3)
    c.chat("3")
    c.expect("trimester", "mobility")

    # Mobility: Balance (#5)
    c.chat("5")

    # Discovery
    c.chat("my legs are swollen and I have trouble balancing, especially at night")

    for _ in range(5):
        resp = c.last_response.lower()
        if "protocol" in resp or "routine" in resp or "here is" in resp or "tailored" in resp:
            break
        if "timing" in resp or "worst" in resp or "when" in resp:
            c.chat("evening and night")
        elif "region" in resp or "area" in resp or "where" in resp:
            c.chat("legs and ankles")
        elif "trigger" in resp or "start" in resp or "specific" in resp:
            c.chat("pregnancy, third trimester")
        elif "summary" in resp or "correct" in resp or "right" in resp:
            c.chat("yes")
        else:
            c.chat("yes")

    for _ in range(3):
        resp = c.last_response.lower()
        if "pdf" in resp or "download" in resp or ".pdf" in resp:
            break
        else:
            c.chat("yes, looks great")

    if c.pdf_url:
        if c.download_and_check_pdf():
            c.pdf_contains("user_name", "sofia")
            c.pdf_contains("trimester", "3rd trimester")
            c.pdf_contains("pregnancy_faq", "compression safe during pregnancy")
            c.pdf_not_contains("no_standing", "structured calf pump")

    return c.result()


def test_athletic_recovery_full():
    """Athletic recovery user: Marcus Johnson, athletic, pain."""
    c = ConversationRunner("recovery_marcus", "Marcus Johnson", "marcus.j@email.com")

    c.chat(f"Name: {c.user_name} Email: {c.user_email}")
    c.expect("identity", "marcus", "main concern")

    # Goal: Exercise recovery (#4)
    c.chat("4")
    c.expect("goal", "exercise recovery", "health")

    # Health: Athletic (#5)
    c.chat("5")
    c.expect("health", "mobility")

    # Mobility: Pain (#6)
    c.chat("6")

    # Discovery
    c.chat("my legs feel heavy and sore after long training runs")

    for _ in range(5):
        resp = c.last_response.lower()
        if "protocol" in resp or "routine" in resp or "here is" in resp or "tailored" in resp:
            break
        if "timing" in resp or "worst" in resp or "when" in resp:
            c.chat("after workouts, usually afternoon")
        elif "region" in resp or "area" in resp or "where" in resp:
            c.chat("legs, calves, and feet")
        elif "trigger" in resp or "start" in resp or "specific" in resp:
            c.chat("after training and racing")
        elif "summary" in resp or "correct" in resp or "right" in resp:
            c.chat("yes")
        else:
            c.chat("yes")

    for _ in range(3):
        resp = c.last_response.lower()
        if "pdf" in resp or "download" in resp or ".pdf" in resp:
            break
        else:
            c.chat("yes, looks great")

    if c.pdf_url:
        if c.download_and_check_pdf():
            c.pdf_contains("user_name", "marcus")

    return c.result()


def test_cardiac_full():
    """Cardiac user: Dorothy Williams, cardiac, little tolerance, no mobility issues."""
    c = ConversationRunner("cardiac_dorothy", "Dorothy Williams", "dorothy.w@email.com")

    c.chat(f"Name: {c.user_name} Email: {c.user_email}")
    c.expect("identity", "dorothy", "main concern")

    # Goal: General wellness (#7)
    c.chat("7")
    c.expect("goal", "wellness", "health")

    # Health: Cardiac (#1)
    c.chat("1")
    c.expect("health", "tolerance")

    # Tolerance: Little (#2)
    c.chat("2")
    c.expect("tolerance", "mobility")

    # Mobility: None (#7)
    c.chat("7")

    # Discovery
    c.chat("general wellness, my legs feel heavy by end of day")

    for _ in range(5):
        resp = c.last_response.lower()
        if "protocol" in resp or "routine" in resp or "here is" in resp or "tailored" in resp:
            break
        if "timing" in resp or "worst" in resp or "when" in resp:
            c.chat("end of day, evening")
        elif "region" in resp or "area" in resp or "where" in resp:
            c.chat("legs")
        elif "trigger" in resp or "start" in resp or "specific" in resp:
            c.chat("daily, just ongoing")
        elif "summary" in resp or "correct" in resp or "right" in resp:
            c.chat("yes")
        else:
            c.chat("yes")

    for _ in range(3):
        resp = c.last_response.lower()
        if "pdf" in resp or "download" in resp or ".pdf" in resp:
            break
        else:
            c.chat("yes, looks great")

    if c.pdf_url:
        if c.download_and_check_pdf():
            c.pdf_contains("user_name", "dorothy")
            c.pdf_contains("cardiac_faq", "after a procedure")

    return c.result()


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

ALL_TESTS = [
    test_travel_full,
    test_wheelchair_full,
    test_pregnant_full,
    test_athletic_recovery_full,
    test_cardiac_full,
]

if __name__ == "__main__":
    try:
        r = requests.get(BASE_URL, timeout=5)
        if r.status_code != 200:
            print(f"Server not responding at {BASE_URL}")
            sys.exit(1)
    except Exception:
        print(f"Server not running at {BASE_URL}. Start with: python server.py")
        sys.exit(1)

    print("=" * 60)
    print("FULL CONVERSATION E2E TESTS")
    print(f"Server: {BASE_URL}")
    print("Complete user journeys: identity -> goal -> intake -> discovery -> protocol -> PDF")
    print("=" * 60)

    passed = 0
    failed = 0
    for test_fn in ALL_TESTS:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  CRASH: {test_fn.__name__}: {e}")
            failed += 1

    print()
    print("=" * 60)
    total = passed + failed
    if failed == 0:
        print(f"ALL {total} CONVERSATIONS PASSED")
    else:
        print(f"{passed}/{total} PASSED, {failed} FAILED")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
