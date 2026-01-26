"""
Semantic Progression Tests
Focus: discovery flow should advance with natural language answers
"""
import random
import time
import requests
from datetime import datetime

BASE_URL = "http://localhost:8000"

REGION_PHRASES = [
    "my shins",
    "top of my feet",
    "instep and ankle area",
    "upper thighs",
    "hip area",
    "glutes",
    "lower back",
    "upper back",
    "collarbone area",
    "jawline and cheeks",
    "forearms",
    "biceps",
    "triceps",
    "wrists and hands",
    "lower belly",
    "midriff",
    "side waist",
    "ribcage",
    "sternum area",
    "whole lower body"
]

CONTEXT_PHRASES = [
    "after a road trip",
    "after a long drive",
    "after air travel",
    "after a flight overseas",
    "during a heat wave",
    "in humid weather",
    "after a gym session",
    "after hot yoga",
    "during pregnancy",
    "after my C section",
    "after a procedure last week",
    "post surgical recovery",
    "after an injury",
    "after long shifts on my feet",
    "after standing all day",
    "after a long day at my desk",
    "after a dance class",
    "after a spin class",
    "after a hike",
    "after a marathon"
]

TIMING_PHRASES = [
    "first thing when I wake",
    "late in the day",
    "by bedtime",
    "around sunset",
    "after dinner",
    "midday",
    "after lunch",
    "all day long",
    "all the time",
    "on and off",
    "comes and goes",
    "no pattern",
    "random",
    "constant",
    "24 7",
    "mostly in the evenings",
    "mostly in the mornings",
    "mostly afternoons",
    "after work",
    "whenever I sit too long"
]


def classify_response(text: str) -> str:
    t = (text or "").lower()
    if "4 to 5 quick questions" in t:
        return "permission"
    if "where in your body" in t or ("legs and feet" in t and "arms and hands" in t):
        return "region"
    if "did this start after" in t or "trigger changes" in t:
        return "context"
    if "when does it feel worst" in t or "timing helps me" in t:
        return "timing"
    if "before i build your protocol" in t or "here is what i heard" in t:
        return "summary"
    return "other"


def send_message(session_id: str, message: str) -> dict:
    try:
        resp = requests.post(
            f"{BASE_URL}/chat",
            json={"message": message, "session_id": session_id},
            timeout=30,
        )
        return {"status": resp.status_code, "data": resp.json()}
    except Exception as e:
        return {"status": 500, "error": str(e)}


def run_test(test_id: int, region: str, context: str, timing: str) -> dict:
    session_id = f"semantic_{int(time.time())}_{random.randint(1000,9999)}"
    steps = [
        ("Event: Start", "permission"),
        ("Alex alex@test.com", "goal"),
        ("I want a lymphatic wellness protocol", "permission"),
        ("yes", "region"),
        (region, "context"),
        (context, "timing"),
        (timing, "summary"),
    ]

    results = []
    for msg, expected in steps:
        resp = send_message(session_id, msg)
        results.append({"input": msg, "output": resp})
        time.sleep(0.1)

    # Evaluate progression at key checkpoints
    checkpoints = [
        (2, ["permission"]),
        (3, ["region"]),
        (4, ["context"]),
        (5, ["timing", "summary"]),
        (6, ["summary", "other"]),
    ]

    passed = True
    reasons = []
    step5_got = None
    for idx, expected_list in checkpoints:
        output = results[idx]["output"]
        if output.get("status") != 200:
            passed = False
            reasons.append(f"HTTP error at step {idx}")
            continue
        text = output.get("data", {}).get("response", "")
        got = classify_response(text)
        if idx == 5:
            step5_got = got
        if got not in expected_list:
            # If step 5 already advanced to summary, step 6 can be any non error response
            if idx == 6 and step5_got == "summary":
                continue
            passed = False
            reasons.append(f"Step {idx} expected {expected_list} got {got}")

    return {
        "test_id": test_id,
        "region": region,
        "context": context,
        "timing": timing,
        "passed": passed,
        "reasons": reasons,
        "response_preview": results[-1]["output"].get("data", {}).get("response", "")[:120] if results else "",
        "conversation": results,
    }


def run_suite(num_tests: int = 50):
    random.seed(7)
    tests = []

    combos = set()
    while len(combos) < num_tests:
        combos.add((
            random.choice(REGION_PHRASES),
            random.choice(CONTEXT_PHRASES),
            random.choice(TIMING_PHRASES),
        ))

    print("=" * 60)
    print("SEMANTIC PROGRESSION TESTS")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    passed = 0
    failed = 0

    for i, (region, context, timing) in enumerate(list(combos), start=1):
        result = run_test(i, region, context, timing)
        tests.append(result)
        if result["passed"]:
            passed += 1
            print(f"OK Test {i}")
        else:
            failed += 1
            print(f"FAIL Test {i}: {', '.join(result['reasons'])}")

    print("\n" + "=" * 60)
    print("SEMANTIC TEST SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    return tests


if __name__ == "__main__":
    run_suite(50)
