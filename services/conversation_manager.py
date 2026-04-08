from typing import Dict, List, Optional
import os
import random
import re
try:
    import spacy
except Exception:
    spacy = None
from services.clinical_library import CLINICAL_PROTOCOLS 
from services.product_catalog import PRODUCT_CATALOG, get_products_for_path 
from services.crm_service import CRMService 
from services.safety_service import SafetyService
from services.schemas import UserSessionState, UserAbilityProfile
from services.redaction import redact_phi
from services.ability_intake_handler import AbilityIntakeHandler
from services.ability_constants import ABILITY_TIERS
from services.research_library import ResearchLibrary
from services.response_interpreter import ResponseInterpreter
from services.decision_router import DecisionRouter
from services.protocol_generator import ProtocolGenerator
from services.refinement_engine import RefinementEngine, ActiveProtocol, ProtocolItem, create_active_protocol_from_library
from services.enterprise_logging import enterprise_logger
from services.ai_summary_service import get_ai_summary_service
from services.protocol_modifier import ProtocolModifier
import logging

# Backend URL for absolute PDF links (required when frontend is on a different domain, e.g. Vercel)
BACKEND_URL = os.environ.get("BACKEND_URL", "").rstrip("/")

# --- Global NLP Config ---
try:
    nlp = spacy.load("en_core_web_sm") if spacy else None
except Exception:
    nlp = None

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TITLE_PREFIXES = {"mr", "mrs", "ms", "dr", "prof", "sir", "madam"}
INVALID_NAME_TOKENS = {"yes", "no", "sure", "ok", "okay", "hello", "hi", "hey", "yo", "is", "name", "email", "lead", "good", "morning", "afternoon", "evening", "thanks", "thank", "you", "greetings"}
INVALID_NAME_VERBS = {"having", "feeling", "experiencing", "dealing", "getting", "hurting", "swelling", "pain", "aches", "aching"}

CARDIO_ITEM_NAMES = {
    "Aerobic Movement",
    "Afternoon Walk",
    "Thoracic Duct Pump Check",
    "Arm Ergometer / Wheelchair Push",
    "Seated Marching",
    "Seated Upper-Body Cardio",
}

# --- Questionnaire Mode: Reusable Option Blocks ---
GOAL_OPTIONS = (
    "○ Swelling or heaviness\n"
    "○ Post-surgery recovery\n"
    "○ Smoother, firmer-looking skin\n"
    "○ Exercise recovery\n"
    "○ Pregnancy comfort\n"
    "○ Travel comfort\n"
    "○ General wellness"
)

_GOAL_DESCRIPTORS = {
    "lighter": "swelling or heaviness",
    "postop": "post-surgery recovery",
    "skin": "skin concerns",
    "recovery": "exercise recovery",
    "pregnancy": "pregnancy discomfort",
    "travel": "travel comfort",
    "wellness": "general wellness"
}

FORK_OPTIONS = (

    "○ Browse compression garments\n"
    "○ Book a consultation\n"
    "○ I'm all set — thank you!"
)

def _is_cardio_item(name: str) -> bool:
    return name in CARDIO_ITEM_NAMES if name else False

def _cardio_contraindicated(state: Optional[UserSessionState], issue_type: str) -> bool:
    if issue_type == "post_op":
        return True
    if state and state.context_trigger == "post_op":
        return True
    profile = state.ability_profile if state else None
    if profile:
        if profile.tier == "cardiac_pulm":
            return True
        if "wheelchair" in profile.accessibility_needs:
            arm_use = profile.accessibility_details.get("wheelchair", {}).get("arm_use")
            if arm_use == "no":
                return True
    return False

def _apply_cardio_policy(items: List[Dict], state: Optional[UserSessionState], issue_type: str) -> List[Dict]:
    if _cardio_contraindicated(state, issue_type):
        return [item for item in items if not _is_cardio_item(item.get("name", ""))]

    if any(item.get("name") == "Aerobic Movement" for item in items):
        return items

    for base_item in CLINICAL_PROTOCOLS.get("foundation", {}).get("items", []):
        if base_item.get("name") == "Aerobic Movement":
            return items + [dict(base_item)]

    return items

def _strip_title(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return ""
    first = parts[0].lower().strip(".,:;")
    if first in TITLE_PREFIXES and len(parts) > 1:
        parts = parts[1:]
    return parts[0].strip(".,:;") if parts else ""

def extract_name(text: str) -> str:
    """
    Extracts a first name from: "Call me Jim", "I am Jim", "Name: Jim", or fallback short msg.
    """
    # 1. Regex Pattern Matching (Priority)
    match = re.search(r"(?:name is|i am|i'm|im|call me|it's|its|this is|name[:\s]+)\s+([a-zA-Z'-]+)", text, re.IGNORECASE)
    if match:
        name = _strip_title(match.group(1))
        if name and name.lower() not in INVALID_NAME_TOKENS and name.lower() not in INVALID_NAME_VERBS:
            # Capitalize the name for consistency
            return name.capitalize()

    # 2. spaCy NER (if available)
    if nlp:
        try:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    name = _strip_title(ent.text)
                    if name and name.lower() not in INVALID_NAME_TOKENS and name.lower() not in INVALID_NAME_VERBS:
                        return name.capitalize()
        except Exception:
            pass

    # 3. Fallback: short message heuristic
    words = [w.strip(".,!?;") for w in text.strip().split() if w.strip(".,!?;")]
    if len(words) <= 2:
        candidate = _strip_title(words[0])
        # Must be alpha and not an email
        if candidate and candidate.isalpha() and "@" not in candidate and candidate.lower() not in INVALID_NAME_TOKENS and candidate.lower() not in INVALID_NAME_VERBS:
            return candidate.capitalize()
    return None

def is_valid_email(email: str) -> bool:
    """Validates email format AND checks for valid TLD."""
    if not email or not EMAIL_REGEX.fullmatch(email):
        return False
    # Extract TLD and validate against common valid TLDs
    tld = email.rsplit(".", 1)[-1].lower()
    VALID_TLDS = {
        "com", "org", "net", "edu", "gov", "io", "co", "us", "uk", "ca", "au", 
        "de", "fr", "es", "it", "nl", "be", "ch", "at", "info", "biz", "me",
        "tv", "cc", "name", "pro", "mobi", "xyz", "online", "site", "app",
        "dev", "tech", "store", "health", "fit", "life", "email", "cloud"
    }
    if tld not in VALID_TLDS:
        return False
    return True

def _normalize_weekly_total(dose: str) -> str:
    if not dose:
        return dose
    pattern = re.compile(
        r"(?P<total>\d+)\s*min/week(?P<tail>[^()]*)\(\s*(?P<per>\d+)\s*min\s*x\s*(?P<days>\d+)\s*days?\s*\)",
        re.IGNORECASE
    )
    def _repl(match: re.Match) -> str:
        total = int(match.group("total"))
        per = int(match.group("per"))
        days = int(match.group("days"))
        calc = per * days
        if calc == total:
            return match.group(0)
        day_word = "day" if days == 1 else "days"
        return f"{calc} min/week{match.group('tail')}({per} min x {days} {day_word})"
    return pattern.sub(_repl, dose)

def redact_emails(text: str) -> str:
    if not text:
        return text
    return EMAIL_REGEX.sub("[EMAIL]", text)

def parse_identity(text: str) -> Dict[str, Optional[str]]:
    """
    Attempts to extract both name and email from a single message.
    """
    email_match = EMAIL_REGEX.search(text)
    email = email_match.group(0) if email_match else None

    name = extract_name(text)
    if name and name.lower() in INVALID_NAME_TOKENS:
        name = None

    # If the extracted name looks like part of the email local name, try a better name
    # [RELAXED] Allowing name even if it's in email local part (e.g. nadia@gmail.com -> Nadia is valid)
    local_part = email.split("@")[0].lower() if email else None

    # If name wasn't found but we have "Name: X" style
    if not name:
        name_match = re.search(r"name[:\s]+([A-Z][a-zA-Z'-]+)", text, re.IGNORECASE)
        if name_match:
            candidate = _strip_title(name_match.group(1))
            if candidate and candidate.lower() not in INVALID_NAME_TOKENS:
                if not local_part or candidate.lower() not in local_part:
                    name = candidate

    # If still missing, try token before email (e.g., "Jessica jessica@test.com")
    if email and not name:
        tokens = text.split()
        for i, tok in enumerate(tokens):
            if email in tok and i > 0:
                candidate = _strip_title(tokens[i - 1])
                if candidate and candidate.isalpha() and candidate.lower() not in INVALID_NAME_TOKENS and candidate.lower() not in INVALID_NAME_VERBS:
                    name = candidate
                break

    # If still missing, try token after email (e.g., "name is x@email.com Chris")
    if email and not name:
        tokens = [t.strip(".,!?;") for t in text.split()]
        for i, tok in enumerate(tokens):
            if email in tok and i + 1 < len(tokens):
                candidate = _strip_title(tokens[i + 1])
                if candidate and candidate.isalpha() and candidate.lower() not in INVALID_NAME_TOKENS and candidate.lower() not in INVALID_NAME_VERBS:
                    name = candidate
                break

    # If still missing, use first reasonable word as name (e.g., "Mike here, mike@test.com")
    if email and not name:
        for tok in text.split():
            candidate = _strip_title(tok)
            if candidate and candidate.isalpha() and candidate.lower() not in INVALID_NAME_TOKENS and candidate.lower() not in INVALID_NAME_VERBS:
                name = candidate
                break

    return {"name": name, "email": email}

def _infer_accessibility_from_text(text: str) -> tuple:
    """
    Heuristic extraction of accessibility needs from free-text constraints.
    """
    t = (text or "").lower()
    if not t:
        return [], None

    detected = []
    wheelchair_arm_use = None

    if re.search(r"\bwheel\s*chair\b|\bwheelchair\b", t):
        detected.append("wheelchair")

    arm_no_use_patterns = [
        r"\b(can't|cannot|unable to)\s+(move|use)\s+(my\s+)?arms\b",
        r"\bno\s+arm\s+use\b",
        r"\bno\s+use\s+of\s+arms\b",
        r"\bparaly(s|z)ed\s+arms\b",
    ]
    if any(re.search(p, t) for p in arm_no_use_patterns):
        wheelchair_arm_use = "no"

    arm_yes_use_patterns = [
        r"\b(can|able to)\s+(use|move)\s+(my\s+)?arms\b",
        r"\barm\s+use\b",
    ]
    if wheelchair_arm_use is None and any(re.search(p, t) for p in arm_yes_use_patterns):
        wheelchair_arm_use = "yes"

    leg_patterns = [
        r"\b(can't|cannot|unable to)\s+(move|use)\s+(my\s+)?legs\b",
        r"\b(no|zero)\s+leg\s+(movement|mobility)\b",
        r"\bleg\s+paralysis\b",
        r"\bparaly(s|z)ed\s+legs\b",
        r"\bimmobile\s+legs\b",
        r"\bnon[-\s]?weight\s*bearing\b",
    ]
    if any(re.search(p, t) for p in leg_patterns) or ("can't move them" in t and "leg" in t):
        detected.append("legs")

    arm_patterns = [
        r"\b(can't|cannot|unable to)\s+(move|use)\s+(my\s+)?arms\b",
        r"\barm\s+paralysis\b",
        r"\bparaly(s|z)ed\s+arms\b",
    ]
    if any(re.search(p, t) for p in arm_patterns):
        detected.append("arms")

    if re.search(r"\b(can't|cannot|unable to)\s+stand\b|\bbalance\s+(is\s+)?difficult\b", t):
        detected.append("balance")

    # Deduplicate while preserving order
    return list(dict.fromkeys(detected)), wheelchair_arm_use

def detect_goal(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if any(k in t for k in ["consult", "consultation", "specialist", "1:1", "one-on-one", "schedule", "appointment"]):
        return "consult"
    if any(k in t for k in ["shop", "buy", "purchase", "products", "leggings", "bra", "tank", "clothing"]):
        return "shop"
    if any(k in t for k in ["protocol", "routine", "help", "support", "wellness", "swelling", "pain", "recovery", "skin", "cellulite", "texture", "smoother", "firmer", "dimple",
                             "travel", "flight", "comfort", "flying", "airplane", "pregnancy", "pregnant",
                             "surgery", "post-op", "lipo", "liposuction", "procedure", "tummy tuck", "bbl"]):
        return "protocol"
    return None

def extract_primary_region(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GENERAL WELLNESS KEYWORDS (100+ phrases)
    # These catch open-ended responses and treat them as general wellness
    # ═══════════════════════════════════════════════════════════════════════════
    GENERAL_WELLNESS_KEYWORDS = [
        # === BODY COVERAGE ===
        "all over", "everywhere", "whole body", "entire body", "general", "overall", 
        "full body", "total body", "head to toe", "everywhere hurts", "all areas",
        
        # === HEALTH & WELLNESS GOALS ===
        "healthy", "health", "wellness", "well-being", "wellbeing", "stay healthy",
        "remain healthy", "get healthy", "be healthy", "feel healthy", "healthier",
        "prevention", "preventive", "preventative", "proactive", "self-care", "self care",
        "maintain", "maintenance", "upkeep", "routine", "daily routine", "lifestyle",
        
        # === FEELING STATES ===
        "feel good", "feel better", "feel great", "feel normal", "feel like myself",
        "feel lighter", "feel less", "improve", "improvement", "relief", "reduce",
        "help with", "help me", "need help", "looking for help", "want to feel",
        
        # === PREGNANCY & LIFE STAGES ===
        "pregnant", "pregnancy", "expecting", "prenatal", "postnatal", "postpartum",
        "having a baby", "with child", "trimester", "maternity", "motherhood",
        "new mom", "breastfeeding", "nursing", "fertility", "trying to conceive",
        "menopause", "perimenopause", "hormonal", "menstrual", "period", "pms",
        "aging", "getting older", "senior", "elderly", "golden years",
        
        # === COMMON SYMPTOMS (GENERAL) ===
        "swelling", "swollen", "puffy", "puffiness", "edema", "fluid", "water retention",
        "bloated", "bloating", "inflammation", "inflamed", "stiff", "stiffness",
        "heavy", "heaviness", "weighted", "tired", "fatigue", "exhausted", "sluggish",
        "achy", "aching", "sore", "soreness", "discomfort", "uncomfortable",
        "tight", "tightness", "pressure", "throbbing", "tingling", "numbness",
        
        # === OPEN-ENDED INTENTS ===
        "just want to", "i want to", "i need to", "i'd like to", "i would like",
        "hoping to", "trying to", "looking to", "want help", "need some help",
        "could use", "would appreciate", "seeking", "searching for", "curious about",
        "interested in", "wondering", "not sure", "don't know", "unsure what",
        
        # === RECOVERY & HEALING ===
        "recover", "recovering", "healing", "heal", "bounce back", "get back to",
        "return to normal", "back to myself", "feel myself again", "restore",
        "rehabilitation", "rehab", "therapy", "treatment", "manage", "managing",
        
        # === LIFESTYLE & ACTIVITY ===
        "active", "stay active", "be active", "get moving", "mobility", "movement",
        "exercise", "workout", "fitness", "training", "sport", "sports", "athlete",
        "desk job", "sitting all day", "on my feet", "standing all day", "sedentary",
        "work from home", "office", "long hours", "shift work", "nurse", "teacher",
        
        # === POST-WORKOUT RECOVERY ===
        "post workout", "post-workout", "after workout", "after training", "after gym",
        "lactate", "lactic acid", "muscle recovery", "recovery", "sore muscles",
        "doms", "foam roll", "foam rolling", "muscle soreness", "stiff after",
        "crossfit", "mma", "hiit", "cardio", "lifting", "weights", "running",
        "marathon", "triathlon", "gym", "after exercise", "cool down", "cooldown",
        
        # === QUALITY OF LIFE ===
        "quality of life", "live better", "better life", "everyday", "daily",
        "long term", "ongoing", "chronic", "persistent", "recurring", "constant",
        "intermittent", "comes and goes", "on and off", "some days", "most days",
        
        # === COSMETIC & AESTHETIC ===
        "cellulite", "dimpling", "skin", "skin texture", "tone", "toning",
        "firm", "firming", "smooth", "smoothing", "contour", "contouring",
        "slim", "slimming", "detox", "cleanse", "flush", "drainage", "toxins",
        
        # === TRAVEL & SITUATIONAL ===
        "travel", "traveling", "flying", "flight", "airplane", "long flight",
        "road trip", "driving", "sitting", "standing", "heat", "hot weather",
        "summer", "humidity", "altitude", "vacation", "work trip",
        
        # === MEDICAL CONDITIONS (GENERAL MENTION) ===
        "lymphedema", "lipedema", "venous", "circulation", "circulatory",
        "dvt", "blood clot", "varicose", "spider veins", "vein", "veins",
        "diabetes", "thyroid", "autoimmune", "fibromyalgia", "arthritis",
        "cancer", "survivor", "treatment side effects", "medication",
        
        # === EMOTIONAL & CONVERSATIONAL ===
        "just curious", "exploring options", "see what", "learn more",
        "understand", "information", "advice", "guidance", "recommendation",
        "suggestion", "tips", "strategies", "solutions", "options", "alternatives"
    ]
    
    if any(w in t for w in GENERAL_WELLNESS_KEYWORDS):
        return "general"
    if any(w in t for w in ["surgery", "post-op", "lipo", "recovery"]):
        return "post_op"
    if any(w in t for w in ["leg", "legs", "lower body", "ankle", "instep", "shin", "shins", "foot", "feet", "calf", "calves", "cankle", "knee", "thigh", "hip", "hips", "glute", "glutes", "butt"]):
        return "legs"
    if any(w in t for w in ["arm", "arms", "hand", "hands", "finger", "fingers", "elbow", "shoulder", "wrist", "wrists", "forearm", "forearms", "bicep", "biceps", "tricep", "triceps"]):
        return "arms"
    if any(w in t for w in ["neck", "face", "jaw", "jawline", "cheek", "cheeks", "collarbone", "head", "migraine", "fog"]):
        return "neck"
    if any(w in t for w in ["abdomen", "belly", "stomach", "lower belly", "bloat", "bloating", "core", "torso", "trunk", "chest", "back", "lower back", "upper back", "midsection", "midriff", "waist", "side waist", "rib", "ribs", "ribcage", "sternum"]):
        return "core"
    return None

def extract_context_trigger(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if any(w in t for w in ["surgery", "post op", "post-op", "lipo", "bbl", "tummy tuck", "recovery", "procedure", "operation", "c section", "cesarean"]):
        return "post_op"
    if any(w in t for w in ["flight", "flying", "plane", "air travel", "travel", "trip", "road trip", "car", "drive", "long drive"]):
        return "travel"
    if any(w in t for w in ["heat", "heat wave", "hot", "summer", "humidity", "humid"]):
        return "heat"
    if any(w in t for w in ["workout", "training", "gym", "session", "run", "running", "marathon", "race", "tennis", "golf", "spin", "cycle", "cycling", "pilates", "yoga", "hot yoga", "dance", "hike", "hiking"]):
        return "workout"
    if any(w in t for w in ["pregnant", "pregnancy", "maternity"]):
        return "pregnancy"
    if any(w in t for w in ["born", "since birth", "congenital", "lifelong", "always had this"]):
        return "daily"
    if any(w in t for w in ["chronic", "no trigger", "no specific trigger", "no clear trigger", "nothing specific", "not sure why", "unknown trigger"]):
        return "daily"
    if any(w in t for w in ["daily", "every day", "all day", "always", "all the time", "ongoing", "standing", "sitting", "desk", "work", "job", "long day", "long shift", "after work", "after a long day"]):
        return "daily"
    return None

def extract_timing(text: str) -> Optional[str]:
    """Extract timing preference from user message with comprehensive phrase matching."""
    if not text:
        return None
    t = text.lower()
    
    # === UNCERTAIN / VARIABLE ===
    UNCERTAIN_PHRASES = [
        "i dont know", "i don't know", "idk", "not sure", "unsure", "no idea", "unknown",
        "hard to say", "varies", "depends", "it changes", "different every day", "unpredictable"
    ]
    if any(w in t for w in UNCERTAIN_PHRASES):
        return "variable"
    
    # === ALL DAY / CONSTANT (expanded) ===
    ALL_DAY_PHRASES = [
        # Direct all-day phrases
        "all day", "all day long", "all the time", "all times", "any time", "anytime",
        "throughout the day", "throughout", "the whole day", "whole day", "entire day",
        
        # Constant/persistent
        "constant", "constantly", "continuous", "continuously", "persistent", "persistently",
        "nonstop", "non-stop", "24 7", "24-7", "24/7", "around the clock", "never stops",
        
        # Always/daily
        "always", "daily", "every day", "everyday", "each day", "day to day",
        
        # Doesn't matter / all options
        "doesnt matter", "doesn't matter", "no difference", "same", "the same",
        "all of them", "all three", "all of the above", "none specifically",
        
        # Off and on / intermittent but constant
        "off and on", "on and off", "comes and goes", "fluctuates", "waxes and wanes",
        
        # Colloquial
        "literally always", "pretty much always", "basically all day", "most of the day",
        "from morning to night", "when i wake up till i sleep", "never really goes away"
    ]
    if any(w in t for w in ALL_DAY_PHRASES):
        return "all_day"
    
    # === MORNING ===
    MORNING_PHRASES = [
        "morning", "mornings", "am", "a.m.", "wake up", "waking up", "when i wake",
        "first thing", "first thing in the morning", "upon waking", "early", "early morning",
        "before noon", "before lunch", "start of day", "beginning of day", "sunrise"
    ]
    if any(w in t for w in MORNING_PHRASES):
        return "morning"
    
    # === AFTERNOON ===
    AFTERNOON_PHRASES = [
        "afternoon", "afternoons", "midday", "mid-day", "mid day", "noon", "noontime",
        "lunch", "lunchtime", "after lunch", "middle of the day", "1pm", "2pm", "3pm", "4pm",
        "early afternoon", "late afternoon", "post-lunch"
    ]
    if any(w in t for w in AFTERNOON_PHRASES):
        return "afternoon"
    
    # === EVENING / NIGHT ===
    EVENING_PHRASES = [
        "evening", "evenings", "night", "nights", "nighttime", "pm", "p.m.",
        "late in the day", "end of day", "end of the day", "after dinner", "dinner time",
        "sunset", "bedtime", "before bed", "going to bed", "lying down",
        "after work", "when i get home", "5pm", "6pm", "7pm", "8pm", "9pm", "10pm",
        "later in the day", "as the day goes on", "by evening", "towards evening"
    ]
    if any(w in t for w in EVENING_PHRASES):
        return "evening"
    
    return None

def _region_keywords(region: Optional[str]) -> list:
    if region == "post_op":
        return ["post-op", "surgery", "lipo"]
    if region == "legs":
        return ["legs", "ankles", "feet"]
    if region == "arms":
        return ["arms", "hands"]
    if region == "neck":
        return ["neck", "face", "jaw"]
    if region == "core":
        return ["abdomen", "bloating"]
    if region == "general":
        return []
    return []

def _context_keywords(context: Optional[str]) -> list:
    if context == "post_op":
        return ["post-op", "surgery", "recovery"]
    if context == "travel":
        return ["travel", "flight", "plane"]
    if context == "heat":
        return ["heat", "hot", "summer"]
    if context == "workout":
        return ["workout", "training", "run"]
    if context == "pregnancy":
        return ["pregnant", "pregnancy"]
    if context == "daily":
        return ["daily"]
    return []

def _is_uncertain(msg: str) -> bool:
    t = (msg or "").lower()
    return any(w in t for w in ["i dont know", "i don't know", "idk", "not sure", "unsure", "no idea", "maybe"])

def _interpret_discovery(msg: str) -> Dict[str, Optional[str]]:
    """
    Holistic interpretation of a reply to infer region, trigger, and timing.
    Returns dict with inferred slots and uncertainty flags.
    """
    t = (msg or "").lower()
    info = {
        "region": None,
        "context": None,
        "timing": None,
        "uncertain_region": False,
        "uncertain_context": False,
        "uncertain_timing": False,
        "region_hits": [],
    }
    if _is_uncertain(t):
        info["uncertain_region"] = True
        info["uncertain_context"] = True
        info["uncertain_timing"] = True

    # Region inference
    region_hits = set()
    if any(w in t for w in ["leg", "legs", "lower body", "ankle", "instep", "shin", "shins", "foot", "feet", "calf", "calves", "cankle", "knee", "thigh", "hip", "hips", "glute", "glutes", "butt"]):
        region_hits.add("legs")
    if any(w in t for w in ["arm", "arms", "hand", "hands", "finger", "fingers", "elbow", "shoulder", "wrist", "wrists", "forearm", "forearms", "bicep", "biceps", "tricep", "triceps"]):
        region_hits.add("arms")
    if any(w in t for w in ["neck", "face", "jaw", "jawline", "cheek", "cheeks", "collarbone", "head", "migraine", "fog"]):
        region_hits.add("neck")
    if any(w in t for w in ["abdomen", "belly", "lower belly", "stomach", "bloat", "bloating", "core", "torso", "trunk", "chest", "back", "lower back", "upper back", "midsection", "midriff", "waist", "side waist", "rib", "ribs", "ribcage", "sternum"]):
        region_hits.add("core")
    if any(w in t for w in ["all over", "everywhere", "whole body", "entire body", "general", "overall", "full body"]):
        region_hits.add("general")

    if len(region_hits) == 1:
        info["region"] = list(region_hits)[0]
    elif len(region_hits) > 1:
        info["region"] = "general"
        info["region_hits"] = list(region_hits)
    else:
        region = extract_primary_region(t)
        if region:
            info["region"] = region

    # Context inference
    context = extract_context_trigger(t)
    if context:
        info["context"] = context
    elif any(w in t for w in ["accident", "injury", "hurt", "trauma"]):
        info["context"] = "daily"

    # Timing inference
    timing = extract_timing(t)
    if timing:
        info["timing"] = timing

    if any(w in t for w in ["comes and goes", "on and off", "off and on", "fluctuates", "varies", "random", "no pattern", "whenever"]):
        info["timing"] = "variable"
    if any(w in t for w in ["constant", "always", "all the time", "all day", "all day long", "24/7", "24 7", "24-7"]):
        info["timing"] = "all_day"
    if any(w in t for w in ["worse at night", "end of day", "late in the day", "after work", "evening", "after a long day", "after long day", "after dinner", "sunset", "by bedtime"]):
        info["timing"] = "evening"
    if any(w in t for w in ["in the morning", "wake up", "when i wake", "morning", "first thing"]):
        info["timing"] = "morning"
    if any(w in t for w in ["midday", "afternoon", "lunch", "after lunch"]):
        info["timing"] = "afternoon"

    if info["timing"] in ("variable", "all_day"):
        info["uncertain_timing"] = False

    return info

def _discovery_empathy(msg: str) -> str:
    t = (msg or "").lower()
    if any(w in t for w in ["pain", "hurt", "aching", "sore"]):
        return "I’m sorry you’re dealing with that. It sounds really uncomfortable."
    if any(w in t for w in ["swelling", "puffy", "heavy", "edema"]):
        return "Thanks for sharing that. Swelling can feel frustrating and heavy."
    if any(w in t for w in ["accident", "injury", "surgery", "post-op", "recovery"]):
        return "I’m sorry that happened. Let’s make this as clear and supportive as possible."
    if any(w in t for w in ["wellness", "prevent", "optimize", "performance", "training"]):
        return "That’s a great goal. I can help tailor this to your routine."
    return "Thanks for sharing. I want to make sure this is tailored to you."

def _is_affirmative(msg: str) -> bool:
    t = (msg or "").lower()
    return any(w in t for w in ["yes", "yep", "yeah", "sure", "ok", "okay", "please", "go ahead", "sounds good"])

def _is_negative(msg: str) -> bool:
    t = (msg or "").lower()
    if any(phrase in t for phrase in ["not now", "prefer not"]):
        return True
    return bool(re.search(r"\b(no|nope|nah|skip|don't|do not)\b", t))

def _is_email_check(msg: str) -> bool:
    t = (msg or "").lower()
    return "email" in t and any(w in t for w in ["what", "which", "have", "on file", "did you save"])

def _is_repeat_frustration(msg: str) -> bool:
    t = (msg or "").lower()
    return any(w in t for w in ["already", "told you", "as i said", "above", "i said"])

def _sanitize_no_dashes(text: str) -> str:
    if not text:
        return text
    urls = {}
    def _protect_url(match):
        key = f"__URL{len(urls)}__"
        urls[key] = match.group(0)
        return key
    # Protect markdown links and URL-like paths before dash normalization
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", _protect_url, text)
    text = re.sub(r"https?://\S+", _protect_url, text)
    text = re.sub(r"/static/\S+", _protect_url, text)
    text = text.replace("—", ". ").replace("–", ". ")
    text = text.replace(" - ", ". ")
    text = re.sub(r"(\d)\s*-\s*(\d)", r"\1 to \2", text)
    text = re.sub(r"(?<=\w)-(?=\w)", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    for key, url in urls.items():
        text = text.replace(key, url)
    return text

def _is_constraint_noise(text: Optional[str]) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(phrase in t for phrase in ["no trigger", "no specific trigger", "unknown trigger"])

def _build_user_summary_core(state: Optional[UserSessionState]) -> Optional[str]:
    if not state:
        return None
    region_map = {
        "legs": "your legs and feet",
        "arms": "your arms and hands",
        "neck": "your face and neck",
        "core": "your abdomen and core",
        "post_op": "post op recovery area",
        "general": "multiple areas",
    }
    context_map = {
        "post_op": "related to surgery or recovery",
        "travel": "related to travel",
        "heat": "related to heat or humidity",
        "workout": "related to workouts",
        "pregnancy": "related to pregnancy",
        "daily": "more of a daily pattern",
    }
    timing_map = {
        "morning": "worse in the morning",
        "afternoon": "worse in the afternoon",
        "evening": "worse in the evening",
        "all_day": "present all day",
        "variable": "on and off",
    }

    sentences = []
    if state.primary_region and state.primary_region in region_map:
        sentences.append(f"You mentioned {region_map[state.primary_region]}.")
    if state.context_trigger and state.context_trigger in context_map:
        sentences.append(f"It seems {context_map[state.context_trigger]}.")
    if state.timing and state.timing in timing_map:
        sentences.append(f"It is {timing_map[state.timing]}.")

    if not sentences:
        return None
    return " ".join(sentences)


def _build_user_summary(state: Optional[UserSessionState]) -> Optional[str]:
    core = _build_user_summary_core(state)
    if not core:
        return None
    return f"Here is what I heard. {core}"


def _build_user_summary_for_protocol(state: Optional[UserSessionState]) -> Optional[str]:
    core = _build_user_summary_core(state)
    if not core:
        return None
    extra = ""
    if state and state.extra_context and state.extra_context not in ("none", "None"):
        extra = f" I'll keep in mind: {state.extra_context}."
    return f"Thanks for your answers. {core}{extra}"

def _get_attempts(state: Optional[UserSessionState], key: str) -> int:
    if not state or not state.question_attempts:
        return 0
    return int(state.question_attempts.get(key, 0))

def _record_question(state: Optional[UserSessionState], key: str) -> Dict[str, object]:
    attempts = {}
    if state and state.question_attempts:
        attempts = dict(state.question_attempts)
    attempts[key] = int(attempts.get(key, 0)) + 1
    return {"last_question_key": key, "question_attempts": attempts}

def _clear_last_question(state: Optional[UserSessionState]) -> Dict[str, object]:
    if not state:
        return {"last_question_key": None}
    return {"last_question_key": None}
logger = logging.getLogger(__name__)

class ConversationManager:
    """
    Manages the conversational state machine for the Elastique Wellness Guide.
    Refactored V3: Implements 'Empathy Sandwich' and 'Educational Bridging' per bot_training_manual.md.
    """
    
    def __init__(self, citation_engine=None, analytics_service=None, mm_service=None, llm_rewriter=None, research_library=None, response_interpreter=None):
        self.citation_engine = citation_engine
        self.analytics = analytics_service
        self.crm = CRMService()
        self.mm_service = mm_service # [NEW] Inject Multimodal Service for Smart ID
        self.llm_rewriter = llm_rewriter
        self.research_library = research_library or ResearchLibrary()
        self.response_interpreter = response_interpreter or ResponseInterpreter()
        self.decision_router = DecisionRouter()
        self.protocol_gen = ProtocolGenerator()
        self.states = {} 

    def get_state(self, session_id: str) -> UserSessionState:
        """
        Returns a validated UserSessionState model.
        """
        if session_id not in self.states:
            self.states[session_id] = UserSessionState(session_id=session_id)
        return self.states[session_id]

    def update_state(self, session_id: str, new_data: Dict):
        """
        Updates the state and re-validates via Pydantic.
        """
        current = self.get_state(session_id)
        # Update model with dictionary data
        updated_data = current.model_dump()
        updated_data.update(new_data)
        self.states[session_id] = UserSessionState(**updated_data)

    # ══════════════════════════════════════════════════════════════
    # COHERENCE VALIDATOR — ensures the state tells a consistent story
    # ══════════════════════════════════════════════════════════════

    _GOAL_TITLES = {
        "travel": "Your Travel Comfort Protocol",
        "pregnancy": "Your Pregnancy Wellness Protocol",
        "postop": "Your Post-Surgery Recovery Protocol",
        "recovery": "Your Exercise Recovery Protocol",
        "skin": "Your Skin & Firmness Protocol",
        "lighter": "Your Swelling & Heaviness Protocol",
        "wellness": "Your Lymphatic Wellness Protocol",
    }

    _GOAL_CONTEXT_MAP = {
        "travel": "travel",
        "pregnancy": "pregnancy",
        "postop": "surgery",
        "recovery": "training",
    }

    _PROFILE_DENY_LISTS = {
        "wheelchair": ["Structured Calf Pump", "Standing Calf Raises", "Afternoon Walk", "Aerobic Movement"],
        "balance": ["Structured Calf Pump", "Standing Calf Raises", "Afternoon Walk", "Aerobic Movement"],
        "arms": ["Upper Body Pump Circuit", "Arm Circles", "Overhead Stretch"],
    }

    def _validate_and_fix_coherence(self, session_id: str, protocol_items: list, title: str) -> tuple:
        """
        Validate that state, protocol items, and title are coherent.
        Auto-corrects what it can, logs what it can't.
        Returns (fixed_title, fixed_items, warnings).
        """
        state = self.get_state(session_id)
        goal_key = state.goal_key or ""
        warnings = []

        # --- 1. Goal ↔ Title ---
        expected_title = self._GOAL_TITLES.get(goal_key)
        if expected_title and expected_title.lower() not in title.lower():
            warnings.append(f"Coherence: Title '{title}' doesn't match goal '{goal_key}'. Auto-corrected to '{expected_title}'.")
            title = expected_title

        # --- 2. Goal ↔ Context Trigger ---
        expected_ctx = self._GOAL_CONTEXT_MAP.get(goal_key)
        if expected_ctx and state.context_trigger != expected_ctx:
            warnings.append(f"Coherence: context_trigger='{state.context_trigger}' doesn't match goal '{goal_key}'. Auto-corrected to '{expected_ctx}'.")
            self.update_state(session_id, {"context_trigger": expected_ctx})

        # --- 3. Profile ↔ Protocol Items (deny-list safety net) ---
        if state.ability_profile and state.ability_profile.accessibility_needs:
            for need in state.ability_profile.accessibility_needs:
                deny_list = self._PROFILE_DENY_LISTS.get(need, [])
                filtered = []
                for item in protocol_items:
                    action = item.get("action", "")
                    if action in deny_list:
                        warnings.append(f"Coherence: Removed '{action}' — contraindicated for '{need}'.")
                    else:
                        filtered.append(item)
                protocol_items = filtered

        # --- 4. Dose sanity — no timed exercise under 2 min, no reps under 10 ---
        import re as _re
        for item in protocol_items:
            dose = str(item.get("details", ""))
            name = item.get("action", "")
            min_match = _re.search(r'(\d+)\s*min', dose, _re.IGNORECASE)
            if min_match and int(min_match.group(1)) < 2:
                warnings.append(f"Coherence: '{name}' has dose '{dose}' under 2 min floor.")
            reps_match = _re.search(r'(\d+)\s*rep', dose, _re.IGNORECASE)
            if reps_match and int(reps_match.group(1)) < 10:
                warnings.append(f"Coherence: '{name}' has dose '{dose}' under 10 rep floor.")

        # --- 5. Tolerance ↔ Tier consistency ---
        if state.ability_profile:
            ap = state.ability_profile
            if ap.exercise_tolerance and ap.tier not in ("cardiac_pulm", "sedentary"):
                warnings.append(f"Coherence: tolerance='{ap.exercise_tolerance}' set but tier='{ap.tier}' (non-clinical). Tolerance may be ignored.")
            if ap.pregnancy_trimester and ap.tier != "pregnant":
                warnings.append(f"Coherence: trimester='{ap.pregnancy_trimester}' set but tier='{ap.tier}' (not pregnant). Trimester may be ignored.")

        # Log warnings
        if warnings:
            for w in warnings:
                logger.warning(w)

        return title, protocol_items, warnings

    async def process_turn(self, session_id: str, user_msg: str, user_email: Optional[str] = None) -> str:
        import time
        _start_time = time.time()

        state = self.get_state(session_id)
        email_context = user_email or (state.user_email if state else None)

        # Telemetry
        if self.analytics:
             self.analytics.track_message(session_id, "user", user_msg)

        # Log User Message to CRM + Enterprise Logger
        enterprise_logger.log_conversation_event(
            session_id=session_id,
            event_type="message_received",
            user_email=email_context,
            msg_preview=user_msg[:50] if len(user_msg) > 50 else user_msg
        )
        if self.crm:
             self.crm.log_interaction(session_id, "user", user_msg, email=email_context, source="user")

        # Session takeover: pause bot replies, keep logging user input
        if self.crm and self.crm.is_takeover_active(session_id):
             # Log the user message but don't auto-reply — admin is handling this chat
             return await self._finalize_response(session_id, user_msg, "", source="system")

        # 0A. Universal Safety Rail (Hard Refusal)
        safety_refusal = SafetyService.check_emergency(user_msg)
        if safety_refusal:
             enterprise_logger.warning("Safety refusal triggered", session_id=session_id, user_email=email_context)
             return await self._finalize_response(session_id, user_msg, safety_refusal, source="system")

        msg_lower = user_msg.lower()
        
        # 0B. Handle System Start / Reset
        if user_msg in ("Event: Start", "Event: Reset"):
            if self.analytics: self.analytics.track_session_start(session_id, {"email_provided": bool(user_email)})

            # Reset: start a fresh protocol build for this user (new session id) without
            # using the CRM "resume" welcome-back messaging.
            if user_msg == "Event: Reset":
                # Ensure this session starts clean even if the same id is reused.
                self.states[session_id] = UserSessionState(session_id=session_id)
                state = self.get_state(session_id)

                if user_email:
                    crm_name = None
                    try:
                        last_active = self.crm.get_last_interaction(user_email) if self.crm else None
                        if last_active and last_active.get("user_name"):
                            crm_name = last_active.get("user_name")
                    except Exception:
                        crm_name = None

                    self.update_state(session_id, {
                        "user_name": crm_name,
                        "user_email": user_email,
                        "stage": "goal_capture",
                    })

                    name_prefix = f"{crm_name}, " if crm_name else ""
                    response = (
                        f"All set, {name_prefix}let's start fresh.\n\n"
                        f"What's the main concern you'd like to address today?\n\n{GOAL_OPTIONS}"
                    )
                    return await self._finalize_response(session_id, user_msg, response)

                # No email available -> go through identity capture again
                self.update_state(session_id, {"stage": "identity_capture"})
                response = ("Hello! I'm **Sarah**, your Lymphatic Wellness Guide.\n\n"
                            "To remember your needs and build your **personalized lymphatic wellness protocol**, "
                            "I just need your **First Name** and a **valid Email Address**.")
                return await self._finalize_response(session_id, user_msg, response)
            
            # Scenario 1: Active Session (Same Session ID)
            if state.user_name:
                self.crm.log_interaction(session_id, "System", "Welcome Back trigger")
                # Return to goal capture so health intake runs before PDF
                self.update_state(session_id, {"goal": "protocol", "stage": "goal_capture"})
                response = (f"Welcome back, {state.user_name}! "
                            "Let's build your personalized lymphatic wellness protocol.\n\n"
                            f"What's the main concern you'd like to address?\n\n{GOAL_OPTIONS}")
                return await self._finalize_response(session_id, user_msg, response)
            
            # Scenario 2: New Session + Known Email (Smart Retention)
            if user_email:
                # [NEW] Check CRM for History
                last_active = self.crm.get_last_interaction(user_email)
                
                if last_active and last_active.get("user_name"):
                    crm_name = last_active["user_name"]
                
                    # Pre-fill State
                    self.update_state(session_id, {
                        "user_name": crm_name,
                        "user_email": user_email,
                        "stage": "goal_capture"
                    })

                    # Smart Context Greeting (Intent-Aware)
                    intent = last_active.get("intent")
                    last_stage = last_active.get("stage")
                    protocol_url = last_active.get("protocol_url")
                    protocol_summary = last_active.get("protocol_summary")

                    if protocol_url and protocol_summary:
                        # PDF was delivered - show summary, re-link PDF, offer new protocol
                        self.update_state(session_id, {"goal": "protocol", "stage": "goal_capture"})
                        response = (f"Welcome back, {crm_name}! Last time I put together your **{protocol_summary}**.\n\n"
                                    f"[Download your protocol again]({protocol_url})\n\n"
                                    f"Would you like to create **another protocol**?\n\n{GOAL_OPTIONS}")
                        return await self._finalize_response(session_id, user_msg, response)
                    elif intent:
                        # In-progress, no PDF yet - offer to resume
                        self.update_state(session_id, {"goal": "protocol", "stage": "goal_capture"})
                        response = (f"Welcome back, {crm_name}! Last time we were working on your "
                                    f"**tailored protocol for your {intent}**.\n\n"
                                    f"Would you like to **continue**, or start fresh?\n\n"
                                    f"○ Continue where we left off\n{GOAL_OPTIONS}")
                        return await self._finalize_response(session_id, user_msg, response)

                    # No specific protocol yet - proceed to goal capture
                    self.update_state(session_id, {"goal": "protocol", "stage": "goal_capture"})
                    response = (f"Welcome back, {crm_name}! "
                                "Let's build your personalized lymphatic wellness protocol.\n\n"
                                f"What's the main concern you'd like to address?\n\n{GOAL_OPTIONS}")
                    return await self._finalize_response(session_id, user_msg, response)

                # Known Email but NO Name in CRM? -> Identity Capture (Strict)
                self.update_state(session_id, {"stage": "identity_capture", "user_email": user_email})
                response = (f"Welcome back! I see you're logged in as {user_email}, but I don't have your first name yet. "
                            "What should I call you?")
                return await self._finalize_response(session_id, user_msg, response)
        
            # If no email provided, start identity capture
            self.update_state(session_id, {"stage": "identity_capture"})
            response = ("Hello! I'm **Sarah**, your Lymphatic Wellness Guide.\n\n"
                    "To remember your needs and build your **personalized lymphatic wellness protocol**, "
                    "I just need your **First Name** and a **valid Email Address**.")
            return await self._finalize_response(session_id, user_msg, response)

        stage = state.stage
        
        # 1. Identity Capture Stage
        if stage == "identity_capture":
            if _is_email_check(user_msg) and state.user_email:
                response = (f"I have your email as **{state.user_email}**. "
                            "What is your **first name** so I can save your profile?")
                return await self._finalize_response(session_id, user_msg, response)
            # A. Check for Email (Strong Signal)
            identity = parse_identity(user_msg)
            email_part = identity.get("email")

            if email_part:
                # [FIX] Strip trailing punctuation from email for Pydantic validation
                email_part = email_part.rstrip(".,!?;")

                # Validate Email
                if not is_valid_email(email_part):
                    response = ("Thanks! That doesn't look like a valid email address. "
                                "I need a **valid email** to remember your needs and build your **custom lymphatic wellness protocol**. "
                                "What's the best email to use?")
                    return await self._finalize_response(session_id, user_msg, response)
                
                # [AI-POWERED] Smart Extraction
                # Pre-fill with Regex result (Strong Signal)
                regex_name = identity.get("name") or extract_name(user_msg)
                
                # Resolve Name: Extracted -> Temp State -> None (Strict Mode: No "Friend" default yet)
                name_part = regex_name
                redact_phi_enabled = os.getenv("REDACT_PHI", "true").lower() == "true"
                if not name_part and self.mm_service and not redact_phi_enabled:
                    try:
                        result = await self.mm_service.extract_identity(redact_phi(user_msg))
                        name_part = result.get("name")
                    except:
                        pass
                
                if not name_part:
                     name_part = state.temp_name

                # Strict Check
                if not name_part:
                    # We have Email, but NO Name. Prompt for Name.
                    self.update_state(session_id, {"user_email": email_part})
                    response = (f"Thanks! I have your email as **{email_part}**. "
                            "To remember your needs and build your **custom lymphatic wellness protocol**, "
                            "what is your **First Name**?")
                    return await self._finalize_response(session_id, user_msg, response)

                email_extracted = email_part
                
                # We have BOTH Name and Email. Proceed to goal capture FIRST.
                self.update_state(session_id, {
                    "stage": "goal_capture",
                    "user_email": email_part,
                    "user_name": name_part
                })
                if self.crm:
                    self.crm.create_or_update_contact(email=email_part, first_name=name_part)

                # If they already described symptoms (beyond just name/email), infer goal and skip to health questions
                # Strip out the email to avoid false matches on email addresses like "travel@test.com"
                msg_without_email = user_msg.lower().replace(email_part.lower(), "") if email_part else user_msg.lower()
                is_diagnosis_keyword = any(w in msg_without_email for w in ["swelling", "ankle", "surgery", "post op", "post-op", "lipo", "hurt", "pain"])
                if is_diagnosis_keyword:
                    self.update_state(session_id, {
                        "goal": "protocol",
                        "stage": "ability_intake",
                        "ability_intake_stage": "health_status",
                        "discovery_permission_asked": True,
                        "discovery_permission_granted": True,
                    })
                    response = (f"Thanks {name_part}! I've saved your profile.\n\n"
                                f"To make sure your protocol is perfectly tailored, I have a few quick questions.\n\n"
                                f"{AbilityIntakeHandler.get_health_status_question()}")
                    return await self._finalize_response(session_id, user_msg, response)

                # Ask goal question first
                response = (f"Thanks {name_part}! Let's build your personalized lymphatic wellness protocol.\n\n"
                            f"What's the main concern you'd like to address or goal you are looking to meet?\n\n{GOAL_OPTIONS}")
                return await self._finalize_response(session_id, user_msg, response)

            # If message contains '@' but no valid email match, prompt for a valid email
            if "@" in user_msg:
                response = ("Thanks! That doesn't look like a valid email address. "
                        "I need a **valid email** to remember your needs and build your **custom lymphatic wellness protocol**. "
                        "What's the best email to use?")
                return await self._finalize_response(session_id, user_msg, response)
            
            # B. Soft Pivot for Interruption / Generic Greeting
            is_diagnosis_keyword = any(w in msg_lower for w in ["swelling", "ankle", "leg", "surgery", "post-op", "lipo", "recovery", "protocol", "product", "leggings"])
            
            if is_diagnosis_keyword:
                response = ("I'd love to help you with that! To remember your needs and build your **custom lymphatic wellness protocol**, "
                        "could you share your **First Name and a valid Email Address**? Then we can dive right into the details.")
                return await self._finalize_response(session_id, user_msg, response)

            # C. Check for Name Only (Using spaCy NER + Robust Logic)
            parsed_name = extract_name(user_msg)
            is_greeting = any(w in msg_lower for w in ["hi", "hello", "hey", "yo"])
            
            if parsed_name and not is_greeting:
                # 1. Check if we already have their email (from previous turn)
                if state.user_email:
                    # Success! We have both. Start ability intake.
                    self.update_state(session_id, {
                        "stage": "ability_intake",
                        "ability_intake_stage": "permission",
                        "user_name": parsed_name
                    })
                    if self.crm:
                         self.crm.create_or_update_contact(email=state.user_email, first_name=parsed_name)
                    
                    # Start ability intake with permission message
                    response = f"Thanks {parsed_name}! I've saved your profile.\n\n{AbilityIntakeHandler.get_permission_message()}"
                    return await self._finalize_response(session_id, user_msg, response)

                # 2. No email yet? Save temp name and ask.
                self.update_state(session_id, {"temp_name": parsed_name}) 
                response = (f"Nice to meet you, {parsed_name}. "
                        "To remember your needs and build your **custom lymphatic wellness protocol**, "
                        "what is the **best email address** to connect your profile?")
                return await self._finalize_response(session_id, user_msg, response)
                
            else:
                response = ("Hello! I'm Sarah, your Lymphatic Wellness Guide. "
                            "To remember your needs and build your **custom lymphatic wellness protocol**, "
                            "I just need your **First Name and a valid Email Address**.")
                return await self._finalize_response(session_id, user_msg, response)

        # 1.5. Ability Intake Stage (NEW: Adaptive Protocol System)
        if stage == "ability_intake":
            response = self._handle_ability_intake(session_id, user_msg)
            return await self._finalize_response(session_id, user_msg, response)

        # 2. Main Diagnosis Logic (The V3 Core)
        if stage == "goal_capture":
            if state.pending_goal_default:
                if _is_affirmative(user_msg):
                    self.update_state(session_id, {"goal": "protocol", "stage": "discovery", "pending_goal_default": False})
                    response = self._handle_discovery(session_id, user_msg)
                    return await self._finalize_response(session_id, user_msg, response)
                if _is_negative(user_msg):
                    self.update_state(session_id, {"pending_goal_default": False})
                else:
                    return await self._finalize_response(
                        session_id,
                        user_msg,
                        "No problem. Most people start with a lymphatic wellness protocol. Does that sound right?"
                    )
            if _is_email_check(user_msg) and state.user_email:
                # Confirm email and continue with protocol flow
                self.update_state(session_id, {"goal": "protocol", "stage": "discovery"})
                response = (f"I have your email as **{state.user_email}**.\n\n"
                            f"Now, let's build your personalized protocol. What's the main concern you'd like to address?\n\n{GOAL_OPTIONS}")
                return await self._finalize_response(session_id, user_msg, response)

            # Map numeric option-button selections to synthetic goal text
            _GOAL_OPTION_MAP = {
                "1": {"text": "swelling heaviness",    "key": "lighter"},
                "2": {"text": "post-surgery recovery", "key": "postop"},
                "3": {"text": "cellulite skin",        "key": "skin"},
                "4": {"text": "recovery training",     "key": "recovery"},
                "5": {"text": "pregnancy",             "key": "pregnancy"},
                "6": {"text": "travel flight comfort",  "key": "travel"},
                "7": {"text": "general wellness",      "key": "wellness"},
            }
            goal_entry = _GOAL_OPTION_MAP.get(user_msg.strip())
            if goal_entry:
                effective_msg = goal_entry["text"]
                updates = {"goal_key": goal_entry["key"]}
                # Pre-set context_trigger for goals that imply a specific trigger
                if goal_entry["key"] == "travel":
                    updates["context_trigger"] = "travel"
                elif goal_entry["key"] == "pregnancy":
                    updates["context_trigger"] = "pregnancy"
                self.update_state(session_id, updates)
            else:
                effective_msg = user_msg
                # Infer goal_key from free-text
                _TEXT_TO_KEY = {
                    "lighter": ["swelling", "swollen", "heaviness", "heavy", "puffy", "puffiness", "edema", "lighter"],
                    "postop": ["surgery", "post-surgery", "post-op", "procedure", "lipo", "liposuction"],
                    "skin": ["cellulite", "skin", "texture", "firmer", "smoother", "dimpling"],
                    "recovery": ["recovery", "training", "workout", "exercise", "sport", "athlete", "running"],
                    "pregnancy": ["pregnant", "pregnancy", "expecting", "trimester", "postpartum"],
                    "travel": ["travel", "flight", "flying", "airplane", "plane", "air travel", "jet lag", "long haul"],
                    "wellness": ["wellness", "general", "maintenance", "healthy", "prevention"],
                }
                msg_l = effective_msg.lower()
                for gk, keywords in _TEXT_TO_KEY.items():
                    if any(w in msg_l for w in keywords):
                        updates = {"goal_key": gk}
                        if gk == "travel":
                            updates["context_trigger"] = "travel"
                        elif gk == "pregnancy":
                            updates["context_trigger"] = "pregnancy"
                        elif gk == "postop":
                            updates["context_trigger"] = "surgery"
                        elif gk == "recovery":
                            updates["context_trigger"] = "training"
                        self.update_state(session_id, updates)
                        break

            goal = detect_goal(effective_msg)
            if not goal:
                symptom_keywords = ["swelling", "swollen", "ankle", "leg", "legs", "pain", "hurt", "ache", "aching", "heavy", "edema", "puffy", "cankle"]
                if any(w in effective_msg.lower() for w in symptom_keywords):
                    self.update_state(session_id, {"goal": "protocol", "stage": "discovery"})
                    response = self._handle_discovery(session_id, effective_msg)
                    return await self._finalize_response(session_id, user_msg, response)
                if _is_uncertain(user_msg):
                    self.update_state(session_id, {"pending_goal_default": True})
                    response = ("No problem. Most people start with a lymphatic wellness protocol. Does that sound right?\n\n"
                                "○ Yes, that sounds good\n"
                                "○ No, I have something else in mind")
                    return await self._finalize_response(session_id, user_msg, response)
                # Re-prompt with option buttons
                response = ("My role is to design wellness protocols tailored to your specific needs.\n\n"
                            f"What's the main concern you'd like to address?\n\n{GOAL_OPTIONS}")
                return await self._finalize_response(session_id, user_msg, response)

            # goal_key was already set above from _GOAL_OPTION_MAP or text inference
            # After goal capture, move to ability intake (health/mobility questions)
            self.update_state(session_id, {
                "goal": goal,
                "stage": "ability_intake",
                "ability_intake_stage": "permission",
            })

            if goal == "consult":
                self.update_state(session_id, {"stage": "consult"})
                response = ("Wonderful. To get you set up, may I have your **best phone number** "
                            "for our specialist to call?")
                return await self._finalize_response(session_id, user_msg, response)

            # Protocol or Shopping intent → go straight to health status (skip permission)
            if goal == "protocol" or goal_key:
                if not goal and goal_key:
                    goal = "protocol"
                self.update_state(session_id, {
                    "goal": goal,
                    "stage": "ability_intake",
                    "ability_intake_stage": "health_status",
                    "discovery_permission_asked": True,
                    "discovery_permission_granted": True,
                })
                state = self.get_state(session_id)  # refresh after update
                goal_desc = _GOAL_DESCRIPTORS.get(state.goal_key, "your concern")
                response = (f"Great \u2014 let's build your **{goal_desc}** protocol.\n\n"
                            f"To make sure it's perfectly tailored, I have a few quick questions.\n\n"
                            f"{AbilityIntakeHandler.get_health_status_question()}")
                return await self._finalize_response(session_id, user_msg, response)

            return await self._finalize_response(session_id, user_msg, "I'm not sure I understood that. Could you clarify your goal?")

        if stage == "discovery":
            response = self._handle_discovery(session_id, user_msg)
            return await self._finalize_response(session_id, user_msg, response)

        if stage == "consult":
            response = ("Thank you. I’ve noted your number and a specialist will reach out shortly. "
                        "Is there anything else you’d like help with today?")
            return await self._finalize_response(session_id, user_msg, response)

        if stage == "diagnosis":
            # [Fail-safe] Late Email Capture
            if "@" in user_msg and not state.user_email:
                 identity = parse_identity(user_msg)
                 email_part = identity.get("email")
                 if email_part and is_valid_email(email_part):
                     self.update_state(session_id, {"user_email": email_part})
                     if self.crm: self.crm.create_or_update_contact(email=email_part, first_name=state.temp_name or "Friend")
                     response = "Got it. Now, tell me more. Are you managing **daily swelling**, or is this specifically for **post op recovery**?"
                     return await self._finalize_response(session_id, user_msg, response)
                 response = ("Thanks! That doesn't look like a valid email address. "
                         "I need a **valid email** to remember your needs and build your **custom lymphatic wellness protocol**. "
                         "What's the best email to use?")
                 return await self._finalize_response(session_id, user_msg, response)

            response = self._handle_diagnosis_v3(session_id, user_msg)
            return await self._finalize_response(session_id, user_msg, response)
            
        elif stage == "agreement":
            response = self._handle_agreement(session_id, user_msg)
            return await self._finalize_response(session_id, user_msg, response)
            
        elif stage == "fork":
            response = self._handle_fork(session_id, user_msg)
            return await self._finalize_response(session_id, user_msg, response)
            
        elif stage == "complete":
            response = ("It was great chatting with you! Your protocol is saved and ready to download anytime.\n\n"
                       "To start a new assessment, just click **Restart Chat** or refresh the page. "
                       "Take care! 😊")
            return await self._finalize_response(session_id, user_msg, response)
            
        response = "I'm listening. Tell me more about what you're feeling in your body today."
        return await self._finalize_response(session_id, user_msg, response)

    async def _finalize_response(self, session_id: str, user_msg: str, response: str, source: str = "bot") -> str:
        state = self.get_state(session_id)
        # Optional: prepend LLM-generated empathy preamble (tailored to last user input)
        if self.llm_rewriter and getattr(self.llm_rewriter, "preamble_enabled", False):
            fallback = getattr(state, "pending_preamble_fallback", None) if state else None
            context = {
                "issue_type": getattr(state, "last_issue_type", None) or getattr(state, "primary_region", None),
                "goal": getattr(state, "goal", None),
            }
            preamble = await self.llm_rewriter.generate_preamble(user_msg, state, context=context)
            prefix = preamble or fallback
            if prefix:
                response = f"{prefix}\n\n{response.lstrip()}"
            if fallback:
                self.update_state(session_id, {"pending_preamble_fallback": None})

        if self.llm_rewriter:
            rewritten = await self.llm_rewriter.rewrite(user_msg, response, state)
            final_response = _sanitize_no_dashes(rewritten)
        else:
            final_response = _sanitize_no_dashes(response)

        # Log Assistant message to CRM with email context
        if self.crm:
            email = state.user_email if state else None
            self.crm.log_interaction(session_id, "assistant", final_response, email=email, source=source)

        return final_response

    def _handle_diagnosis_v3(self, session_id, msg):
        """
        V3 Implementation of 'Empathy Sandwich'
        Layer 1: Validation (Visual/Text)
        Layer 2: Education (Mechanism)
        Layer 3: Prescription (Linked Protocol)
        """
        msg_lower = msg.lower()
        
        # --- A. Context Detection (Goal-Aware) ---
        is_photo = "photo" in msg_lower or "analyzing tissue" in msg_lower or "jpg" in msg_lower

        # Consult goal_key FIRST — this is what the user explicitly chose
        state = self.get_state(session_id)
        _GOAL_TO_ISSUE = {
            "travel": "legs",
            "pregnancy": "legs",
            "postop": "post_op",
            "recovery": "recovery",
            "skin": "foundation",
            "wellness": "foundation",
            "lighter": None,  # Detect from message (could be legs, arms, etc.)
        }
        goal_issue = _GOAL_TO_ISSUE.get(state.goal_key)

        # Detect region hits from message for secondary context (empathy, multi-region)
        region_hits = set()
        if any(w in msg_lower for w in ["leg", "ankle", "foot", "feet", "calf", "calves", "cankle"]):
            region_hits.add("legs")
        if any(w in msg_lower for w in ["arm", "hand", "finger", "elbow"]):
            region_hits.add("arms")
        if any(w in msg_lower for w in ["neck", "face", "jaw"]):
            region_hits.add("neck")

        if goal_issue:
            # Goal provides the issue_type — don't let keyword detection override it
            issue_type = goal_issue
        else:
            # Fallback: keyword detection for "lighter" (swelling) and unknown goals
            issue_type = "foundation"
            if any(w in msg_lower for w in ["surgery", "post-op", "post_op", "postop", "lipo"]):
                issue_type = "post_op"
            elif len(region_hits) > 1:
                region_list = sorted(list(region_hits))
                if len(region_list) == 2:
                    issue_type = f"{region_list[0]} and {region_list[1]}"
                else:
                    issue_type = ", ".join(region_list[:-1]) + f", and {region_list[-1]}"
            elif len(region_hits) == 1:
                issue_type = list(region_hits)[0]

        # Persist last issue type for downstream empathy/preamble generation
        self.update_state(session_id, {"last_issue_type": issue_type})
            
        # [NEW] Log Primary Intent to CRM for Smart Retention
        state = self.get_state(session_id)
        if self.crm and state.user_email and issue_type != "foundation":
             try:
                 self.crm.log_conversation_start(session_id, state.user_email, intent=issue_type)
             except Exception as e:
                 logger.error(f"CRM Logging Failed: {e}")

        # [CRITICAL UPDATE] Handle Generic Greetings / Low Context
        # If no specific issue detected and message is short/generic, DO NOT prescribe.
        is_generic = issue_type == "foundation" and (len(msg.split()) < 5 or any(w in msg_lower for w in ["hi", "hello", "hey", "start", "help"]))
        if is_generic and not is_photo:
             return ("Hi there! I'm Sarah. To give you the best recommendation, tell me a bit about what's going on.\n\n"
                     "Are you managing **daily swelling/heaviness**, recovering from **surgery**, or looking for **general wellness**?")

        # Select Protocol
        if issue_type == "multi":
            selected_protocols = [CLINICAL_PROTOCOLS.get(hit) for hit in region_hits if CLINICAL_PROTOCOLS.get(hit)]
            selected_protocol = {"title": "Multi-Region Protocol", "items": []}
            seen = set()
            for proto in selected_protocols:
                for item in proto.get("items", []):
                    name = item.get("name")
                    if name and name not in seen:
                        seen.add(name)
                        selected_protocol["items"].append(item)
        else:
            selected_protocol = CLINICAL_PROTOCOLS.get(issue_type, CLINICAL_PROTOCOLS["foundation"])
        
        # 1. Intent Bifurcation (Restorative vs. Performance)
        # Check for Performance/Active Lifestyle keywords
        PERFORMANCE_KEYWORDS = ["sport", "run", "gym", "training", "marathon", "dance", 
                               "prevent", "wellness", "hike", "travel", "flight", "active"]
        INJURY_KEYWORDS = ["pain", "surgery", "hurt", "broke", "lipo", "recovery", "swollen", "bi-lat"]
        
        is_performance = any(w in msg.lower() for w in PERFORMANCE_KEYWORDS)
        is_injury = any(w in msg.lower() for w in INJURY_KEYWORDS)
        
        # Default to restorative if injury is mentioned, even if sport is mentioned (e.g., "running hurts")
        empathy_mode = "performance" if (is_performance and not is_injury) else "restorative"
        self.update_state(session_id, {"empathy_mode": empathy_mode})

        # --- B. Layer 1: Empathy (Validation) ---
        intro = ""
        if is_photo:
            if issue_type == "legs":
                intro = "Thanks for sending the photo. **I can see the tissue density around the ankle specifically.** That looks heavy and uncomfortable to walk on."
            elif issue_type == "post_op":
                intro = "I see the bruising in the photo. Recovery is a journey, and that inflammation is your body's way of protecting itself, but it can feel stiff."
            elif issue_type == "multi":
                intro = "Thanks for the visual. I can see why multiple areas feel heavy. We can work both regions safely."
            else:
                intro = "Thanks for the visual. I can see exactly what you mean about the swelling there."
        else:
            # Text only empathy (Dynamic Bifurcation)
            if empathy_mode == "performance":
                intro = (f"That's exciting! It's great you're prioritizing movement. "
                         f"Let's support that active lifestyle and keep your body feeling light.")
            
            # Restorative Fallbacks
            elif issue_type == "legs":
                intro = "I hear you. Heavy legs at the end of the day are a classic sign that gravity is winning the battle against your circulation."
            elif issue_type == "post_op":
                intro = "I understand completely. Post op swelling is tricky because we want to move the fluid without disturbing the healing tissue."
            elif issue_type == "arms":
                intro = "That heaviness in the arms can be frustrating. It often happens when the axillary (armpit) pathway is sluggish."
            elif issue_type == "multi":
                intro = "Thanks for sharing that. When multiple areas feel swollen, we can sequence a routine that supports both safely."
            else:
                 # Foundation / Default
                intro = "Thanks for sharing. It sounds like you want to support your body's natural flow, which is the foundation of energy and health."

        # Allow LLM to generate the empathy preamble, keep a fallback intro
        use_llm_preamble = bool(self.llm_rewriter and getattr(self.llm_rewriter, "preamble_enabled", False))
        if use_llm_preamble:
            self.update_state(session_id, {"pending_preamble_fallback": intro})
            intro = ""

        # --- C. Layer 2: Education (The Bridge) ---
        bridge = ""
        bridge_core = ""
        if issue_type == "legs":
            bridge_core = ("\n\n**Here is the underlying mechanics:**\n"
                           "Your lymphatic system is unique because **it doesn't have a heart to pump it** like your blood does. "
                           "It relies entirely on movement. When fluid pools in the ankles, it means the return flow is struggling against gravity.")
        elif issue_type == "post_op":
            bridge_core = ("\n\n**Here is the goal:**\n"
                           "Your body is currently in 'protection mode', holding onto fluid. Our goal is to gently open the 'drains' (near the collarbone) "
                           "to create a vacuum effect, pulling that fluid away from the surgical site safely.")
        elif issue_type == "arms":
             bridge_core = ("\n\n**Here is what's happening:**\n"
                            "The axillary (armpit) lymph nodes are the main drain for the arms. When they get congested or stagnant, "
                            "fluid backs up into the hands and triceps. We need to clear the drain first.")
        elif issue_type == "multi":
             bridge_core = ("\n\n**Here is the underlying mechanics:**\n"
                            "When multiple regions feel heavy, we want to open the central pathways first and then sequence movement for each area. "
                            "That improves overall flow without overloading any one region.")
        else:
             bridge_core = ("\n\n**Here is the science:**\n"
                            "The lymphatic system is your body's sewage treatment plant. Without a pump, it needs specific targeted movements "
                            "(like deep breathing) to create the pressure changes that move fluid.")

        summary = _build_user_summary(state)
        if summary:
            bridge = f"\n\n{summary}"
        bridge += bridge_core

        # [NEW] Micro-value insert (science-backed), if available
        micro_value = None
        if self.research_library:
            region_hint = state.primary_region or (issue_type if issue_type in {"legs", "arms", "neck", "post_op", "core"} else None)
            context_hint = state.context_trigger or extract_context_trigger(msg_lower)
            micro_value = self.research_library.find_micro_value(msg_lower, region=region_hint, context=context_hint)
        if micro_value:
            bridge += f"\n\n**Science Snapshot:** {micro_value}"

        # --- D. Layer 3: Conversational Protocol (The Prescription) ---
        # [ADAPTIVE PROTOCOL] Apply ability-based modifications
        protocol_items_raw = _apply_cardio_policy(selected_protocol.get('items', []), state, issue_type)
        ability_profile = state.ability_profile
        
        if ability_profile and ability_profile.intake_completed:
            # Apply dose multipliers, accessibility filters, pregnancy mods
            modified_items = ProtocolModifier.modify_protocol(
                protocol_items_raw,
                ability_profile,
                session_id=session_id
            )
            # Add ability summary to prescription header
            ability_summary = ProtocolModifier.get_protocol_summary_for_ability(ability_profile)
            enterprise_logger.log_protocol_generated(
                session_id=session_id,
                protocol_title=selected_protocol.get('title', 'Unknown'),
                ability_tier=ability_profile.tier,
                multiplier=ability_profile.tier_multiplier if hasattr(ability_profile, 'tier_multiplier') else None
            )
        else:
            modified_items = protocol_items_raw
            ability_summary = None
        
        # Improved Formatting for readability
        prescription = ["\n\n**Here is a Science Backed Routine tailored for you:**"]
        if ability_summary:
            prescription.append(f"\n_({ability_summary})_")
        
        for item in modified_items:
            # Create conversational linkage
            item_name = item['name']
            instruction = item['instruction']
            
            # Formatted Item
            prescription.append(f"\n*   **{item_name}**")
            
            # Justification (The Link)
            link = ""
            if "Calf" in item_name: link = "This acts as your 'second heart' to manually pump fluid back up."
            elif "Breathing" in item_name: link = "This stimulates the Thoracic Duct, the main highway for lymph fluid."
            elif "Elevation" in item_name: link = "This gives your system a break, letting gravity work *for* you."
            elif "Walk" in item_name: link = "Rhythmic walking engages the foot pump with every step."
            elif "MLD" in item_name: link = "This gentle skin stretching manually opens the initial lymph capillaries."
            
            if link:
                prescription.append(f"    *Why?* {link}")
            
            prescription.append(f"    *Do:* {instruction}")

            # [NEW] Dosage Information
            dose = _normalize_weekly_total(item.get("dose")) if item.get("dose") else None
            if dose:
                prescription.append(f"    *Dose:* {dose}")

            # Evidence & Citations
            urls = item.get("urls", [])
            if self.research_library:
                urls = self.research_library.filter_valid_urls(urls)
            
            if urls:
                footer = f"    _([Source]({urls[0]}))_"
                prescription.append(footer)

        # --- E. Layer 4: The Tool (Product Recommendation) ---
        # The "Soft Sell" - positioned as a tool to support the habit
        goal_key = state.goal_key or "wellness"
        
        # Default product logic based on issue_type (region)
        product = PRODUCT_CATALOG.get(issue_type)
        if issue_type == "multi":
            # Prefer legs if included, else arms
            if "legs" in region_hits:
                product = PRODUCT_CATALOG.get("legs")
            elif "arms" in region_hits:
                product = PRODUCT_CATALOG.get("arms") or PRODUCT_CATALOG.get("bra")

        # Goal-Specific Overrides or Phrasing
        if goal_key == "skin" and not product:
            product = PRODUCT_CATALOG.get("bra") # Bra is a common skin-focused recommendation

        if product:
            if goal_key == "skin":
                intro_text = f"To help with {(_GOAL_DESCRIPTORS.get('skin'))}, many of our clients use the **{product['name']}** as a supportive tool."
            else:
                intro_text = f"To make this habit easier, many clients use the **{product['name']}**."
            
            prescription.append("\n\n**Supportive Tool:**")
            prescription.append(f"\n{intro_text}")
            prescription.append(f"\n> *{product['mechanism']}*")
            prescription.append(f"\n[Show Me]({product['url']})")


        # --- F. Closing ---
        closing = ("\n\nDoes this routine feel manageable, or would you like any changes or questions before we finalize it?\n\n"
                   "○ Yes, looks good!\n"
                   "○ I'd like to adjust\n"
                   "○ Can I ask a question?")
        
        # Combine
        full_response = intro + bridge + "".join(prescription) + closing
        
        # Update State
        protocol_items = []
        active_items = []
        for item in modified_items:
            action = item.get("name")
            normalized_dose = _normalize_weekly_total(item.get("dose")) if item.get("dose") else None
            details = normalized_dose or item.get("instruction")
            if action and details:
                protocol_items.append({
                    "action": action,
                    "details": details,
                    "instruction": item.get("instruction"),
                    "urls": item.get("urls", []),
                    "evidence": item.get("evidence"),
                    "mechanism": item.get("mechanism"),
                    "adjustment_note": item.get("adjustment_note"),
                    "segment": item.get("segment"),
                })
            if action:
                active_items.append(
                    ProtocolItem(
                        name=action,
                        instruction=item.get("instruction", ""),
                        dose_text=normalized_dose or item.get("instruction", ""),
                        urls=item.get("urls", []) or []
                    )
                )

        active_protocol = ActiveProtocol(title=selected_protocol.get("title", "Protocol"), items=active_items)
        self.update_state(
            session_id,
            {
                "stage": "agreement",
                "agreed_protocol": [selected_protocol['title']],
                "protocol_items": protocol_items,
                "active_protocol_data": active_protocol.to_dict()
            }
        )
        
        return full_response

    def _handle_ability_intake(self, session_id: str, msg: str) -> str:
        """
        Handles the ability intake stages: permission, health_status, mobility, and follow-ups.
        Collects user's ability profile for personalized protocol generation.
        """
        state = self.get_state(session_id)
        intake_stage = state.ability_intake_stage or "permission"
        msg_lower = msg.lower()
        
        # Initialize ability profile if not exists
        if not state.ability_profile:
            self.update_state(session_id, {"ability_profile": UserAbilityProfile()})
            state = self.get_state(session_id)
        
        profile = state.ability_profile
        
        # ==========================================
        # STAGE: Permission (asking to start intake)
        # ==========================================
        if intake_stage == "permission":
            # User confirms they're ready to start
            if any(w in msg_lower for w in ["yes", "ready", "start", "sure", "ok", "okay", "let's go", "yep", "yeah"]):
                self.update_state(session_id, {
                    "ability_intake_stage": "health_status",
                    "intake_reprompt_count": 0,
                    "discovery_permission_granted": True,
                    "discovery_permission_asked": True
                })
                return AbilityIntakeHandler.get_health_status_question()

            elif any(w in msg_lower for w in ["no", "skip", "later", "not now"]):
                # Skip ability intake - use defaults
                profile.tier = "average"
                profile.intake_completed = True
                self.update_state(session_id, {
                    "ability_profile": profile,
                    "ability_intake_stage": None,
                    "stage": "discovery",
                    "goal": "protocol"
                })
                return (f"No problem, {state.user_name}! We'll use standard protocols.\n\n"
                        f"Now tell me — **what's the main issue you'd like to address?**\n\n"
                        f"{GOAL_OPTIONS}")
            else:
                # Re-prompt permission
                return AbilityIntakeHandler.get_permission_message()
        
        # ==========================================
        # STAGE: Health Status (checkbox selection)
        # ==========================================
        if intake_stage == "health_status":
            selected_tiers = AbilityIntakeHandler.parse_health_status_response(msg)
            
            if selected_tiers is None:
                if state.intake_reprompt_count >= 2:
                    # Forced pass after 3 attempts
                    logger.warning(f"RetryGuard: Forced health_status for {session_id}")
                    selected_tiers = ["average"]
                else:
                    # Re-prompt
                    self.update_state(session_id, {"intake_reprompt_count": state.intake_reprompt_count + 1})
                    return "I didn't quite catch that. " + AbilityIntakeHandler.get_health_status_question()

            
            # Decouple systemic health (multiplier) from mobility (modifications)
            has_limited_limbs = "limited_limbs" in (selected_tiers or [])
            active_health_tiers = [t for t in (selected_tiers or []) if t != "limited_limbs"]
            
            # Prefer the most conservative health tier for dosage
            tier_priority = ["cardiac_pulm", "sedentary", "pregnant", "average", "athletic"]
            primary_tier = next((tier for tier in tier_priority if tier in active_health_tiers), "average")
            
            profile.tier = primary_tier
            profile.has_limb_limitations = has_limited_limbs
            # Track all selected health tiers for combo follow-ups (e.g. cardiac + pregnant)
            profile.all_health_tiers = active_health_tiers

            self.update_state(session_id, {
                "ability_profile": profile,
                "intake_reprompt_count": 0
            })

            # Determine which follow-ups are needed based on ALL selected tiers
            needs_tolerance = any(
                ABILITY_TIERS.get(t, {}).get("followup_type") == "tolerance"
                for t in active_health_tiers
            )
            needs_trimester = "pregnant" in active_health_tiers

            # Ask tolerance first (if needed), then trimester will be checked after
            if needs_tolerance:
                self.update_state(session_id, {
                    "ability_intake_stage": "tolerance_followup",
                    "pending_ability_followup": "tolerance"
                })
                return AbilityIntakeHandler.get_tolerance_question()
            elif needs_trimester:
                self.update_state(session_id, {
                    "ability_intake_stage": "trimester_followup",
                    "pending_ability_followup": "trimester"
                })
                return AbilityIntakeHandler.get_trimester_question()
            
            # Always ask mobility — users who have no considerations can select "None" in one click
            self.update_state(session_id, {"ability_intake_stage": "mobility"})
            return AbilityIntakeHandler.get_mobility_question()
        
        # ==========================================
        # STAGE: Tolerance Follow-up
        # ==========================================
        if intake_stage == "tolerance_followup":
            tolerance = AbilityIntakeHandler.parse_tolerance_response(msg)
            if tolerance or state.intake_reprompt_count >= 2:
                if not tolerance:
                    logger.warning(f"RetryGuard: Forced tolerance for {session_id}")
                    tolerance = "moderate"
                
                profile.exercise_tolerance = tolerance
                self.update_state(session_id, {
                    "ability_profile": profile,
                    "pending_ability_followup": None,
                    "intake_reprompt_count": 0
                })

                # Check if trimester is also needed (cardiac + pregnant combo)
                all_tiers = getattr(profile, 'all_health_tiers', [])
                if "pregnant" in all_tiers and not profile.pregnancy_trimester:
                    self.update_state(session_id, {
                        "ability_intake_stage": "trimester_followup",
                        "pending_ability_followup": "trimester"
                    })
                    return AbilityIntakeHandler.get_trimester_question()

                self.update_state(session_id, {"ability_intake_stage": "mobility"})
                return AbilityIntakeHandler.get_mobility_question()
            else:
                # Re-prompt
                self.update_state(session_id, {"intake_reprompt_count": state.intake_reprompt_count + 1})
                return "I didn't quite catch that. " + AbilityIntakeHandler.get_tolerance_question()
        
        # ==========================================
        # STAGE: Trimester Follow-up
        # ==========================================
        if intake_stage == "trimester_followup":
            trimester = AbilityIntakeHandler.parse_trimester_response(msg)
            if trimester or state.intake_reprompt_count >= 2:
                if not trimester:
                    logger.warning(f"RetryGuard: Forced trimester for {session_id}")
                    trimester = "t2"
                
                profile.pregnancy_trimester = trimester
                self.update_state(session_id, {
                    "ability_profile": profile,
                    "ability_intake_stage": "mobility",
                    "pending_ability_followup": None,
                    "intake_reprompt_count": 0
                })
                return AbilityIntakeHandler.get_mobility_question()
            else:
                self.update_state(session_id, {"intake_reprompt_count": state.intake_reprompt_count + 1})
                return "I didn't quite catch that. " + AbilityIntakeHandler.get_trimester_question()
        
        # ==========================================
        # STAGE: Mobility (checkbox selection)
        # ==========================================
        if intake_stage == "mobility":
            selected_needs = AbilityIntakeHandler.parse_mobility_response(msg)
            if selected_needs is None:
                if state.intake_reprompt_count >= 2:
                    logger.warning(f"RetryGuard: Forced mobility for {session_id}")
                    selected_needs = [] # "None of the above" behavior
                else:
                    self.update_state(session_id, {"intake_reprompt_count": state.intake_reprompt_count + 1})
                    return "I didn't quite catch that. " + AbilityIntakeHandler.get_mobility_question()
            
            # Reset counter on success
            self.update_state(session_id, {"intake_reprompt_count": 0})

            profile.accessibility_needs = selected_needs

            # [REFINEMENT] If user selected "limited limbs" but picked "None" here, re-prompt
            if profile.has_limb_limitations and not selected_needs:
                self.update_state(session_id, {"intake_reprompt_count": state.intake_reprompt_count + 1})
                return ("You mentioned having limited limb use earlier—could you specify which limb(s)? "
                        "This helps me build a safer protocol for you.\n\n" + AbilityIntakeHandler.get_mobility_question())

            msg_lower = msg.lower() if msg else ""
            no_use_phrases = ["no use", "cannot use", "can't use", "unable to use", "paralyzed", "paralysed", "no movement", "no mobility"]
            if any(p in msg_lower for p in no_use_phrases):
                if any(w in msg_lower for w in ["arm", "arms", "hand", "hands"]):
                    profile.accessibility_details["arms"] = {"function": "none"}
                if any(w in msg_lower for w in ["leg", "legs", "foot", "feet"]):
                    profile.accessibility_details["legs"] = {"function": "none"}

            self.update_state(session_id, {"ability_profile": profile})

            if "wheelchair" in selected_needs:
                self.update_state(session_id, {
                    "ability_intake_stage": "wheelchair_arms",
                    "pending_ability_followup": "wheelchair_arms"
                })
                return AbilityIntakeHandler.get_wheelchair_arms_question()
            
            # SIDE CLARIFICATION REMOVED: Bypassing and completing intake
            return self._complete_ability_intake(session_id)

        # ==========================================
        # STAGE: Wheelchair Arm-Use Follow-up
        # ==========================================
        if intake_stage == "wheelchair_arms":
            arm_use = AbilityIntakeHandler.parse_wheelchair_arms_response(msg)
            if arm_use or state.intake_reprompt_count >= 2:
                if not arm_use:
                    logger.warning(f"RetryGuard: Forced wheelchair_arms for {session_id}")
                    arm_use = "yes"
                
                profile.accessibility_details["wheelchair"] = {"arm_use": arm_use}
                if arm_use == "no":
                    for need in ["arms", "hands"]:
                        if need not in profile.accessibility_needs:
                            profile.accessibility_needs.append(need)
                    profile.accessibility_details["arms"] = {"side": "both", "function": "none"}
                self.update_state(session_id, {
                    "ability_profile": profile,
                    "pending_ability_followup": None,
                    "intake_reprompt_count": 0
                })

                # SIDE CLARIFICATION REMOVED: Competing intake immediately after wheelchair arms follow-up
                return self._complete_ability_intake(session_id)
            else:
                self.update_state(session_id, {"intake_reprompt_count": state.intake_reprompt_count + 1})
                return "I didn't quite catch that. " + AbilityIntakeHandler.get_wheelchair_arms_question()

        # SIDE CLARIFICATION STAGES REMOVED (side_arms, side_legs)
        
        # Fallback
        return AbilityIntakeHandler.get_permission_message()
    
    def _complete_ability_intake(self, session_id: str) -> str:
        """
        Complete the ability intake process and transition to goal capture.
        """
        state = self.get_state(session_id)
        profile = state.ability_profile

        # Ensure wheelchair arm-use is captured before completing
        if profile and "wheelchair" in profile.accessibility_needs:
            wheelchair_details = profile.accessibility_details.get("wheelchair", {})
            if not wheelchair_details.get("arm_use"):
                self.update_state(session_id, {
                    "ability_profile": profile,
                    "ability_intake_stage": "wheelchair_arms",
                    "pending_ability_followup": "wheelchair_arms"
                })
                return AbilityIntakeHandler.get_wheelchair_arms_question()

        profile.intake_completed = True

        # Pre-fill discovery slots based on goal_key to skip redundant questions
        goal_key = state.goal_key or ""
        prefill = {}
        if goal_key == "travel":
            prefill = {"primary_region": "legs", "context_trigger": "travel", "timing": "variable",
                       "discovery_slots": {"region": True, "context": True, "timing": True}}
        elif goal_key == "pregnancy":
            prefill = {"primary_region": "legs", "context_trigger": "pregnancy", "timing": "variable",
                       "discovery_slots": {"region": True, "context": True, "timing": True}}
        elif goal_key == "postop":
            prefill = {"context_trigger": "surgery",
                       "discovery_slots": {"context": True}}
        elif goal_key == "recovery":
            prefill = {"context_trigger": "training",
                       "discovery_slots": {"context": True}}

        self.update_state(session_id, {
            "ability_profile": profile,
            "ability_intake_stage": None,
            "pending_ability_followup": None,
            "stage": "discovery",
            "discovery_permission_granted": True,
            "discovery_permission_asked": True,
            **prefill,
        })

        # Save to CRM
        if self.crm and state.user_email:
            try:
                self.crm.update_contact(
                    email=state.user_email,
                    ability_tier=profile.tier,
                    exercise_tolerance=profile.exercise_tolerance,
                    pregnancy_trimester=profile.pregnancy_trimester,
                    accessibility_needs=profile.accessibility_needs,
                    accessibility_details=profile.accessibility_details,
                    intake_completed=True
                )
            except Exception as e:
                import logging
                logging.getLogger("ElastiqueBot").error(f"CRM Update Failed in _complete_ability_intake: {e}")
        
        try:
            # Check if all discovery slots are pre-filled (travel, pregnancy)
            state = self.get_state(session_id)
            all_slots_ready = state.primary_region and state.context_trigger and state.timing

            if all_slots_ready:
                # All slots pre-filled — generate protocol immediately
                summary_msg = AbilityIntakeHandler.get_intake_complete_message(
                    profile, state.user_name or "friend", ready_to_generate=True)

                # Build and return protocol + PDF in one shot
                synthetic_msg = f"{state.primary_region} {state.context_trigger} {state.timing}"
                protocol_response = self._handle_diagnosis_v3(session_id, synthetic_msg)
                state = self.get_state(session_id)
                pdf_msg = self._handle_agreement(session_id, "yes")

                return f"{summary_msg}\n\n---\n\n{pdf_msg}"

            return AbilityIntakeHandler.get_intake_complete_message(profile, state.user_name or "friend")
        except Exception as e:
            import logging
            logging.getLogger("ElastiqueBot").error(f"Error building intake summary: {e}")
            return "Thanks! Profile updated. Now, what's the main issue you'd like to address?"

    def _handle_discovery(self, session_id: str, msg: str) -> str:
        """
        One-question-per-turn discovery flow.
        Collects goal-specific context before generating protocol.
        """
        state = self.get_state(session_id)
        msg_lower = (msg or "").lower()
        interpreted = _interpret_discovery(msg)
        llm_interpreted = self.response_interpreter.interpret(msg) if self.response_interpreter else {}
        llm_conf = (llm_interpreted or {}).get("confidence", "low")
        llm_ok = llm_conf in ("medium", "high")
        router_interpreted = self.decision_router.interpret_discovery(msg) if self.decision_router else {}
        router_conf = (router_interpreted or {}).get("confidence", "low")
        router_ok = router_conf in ("medium", "high")

        # Infer accessibility constraints from free text (e.g., wheelchair, can't move legs)
        if not state.ability_profile:
            self.update_state(session_id, {"ability_profile": UserAbilityProfile()})
            state = self.get_state(session_id)
        profile = state.ability_profile
        inferred_access, inferred_wheelchair_arm = _infer_accessibility_from_text(f"{msg} {state.extra_context or ''}")

        def _build_synthetic_msg(base_msg: str) -> str:
            msg_for_protocol = base_msg or ""
            if len(msg_for_protocol.strip().split()) <= 2 and state.primary_region and state.context_trigger and state.timing:
                msg_for_protocol = ""
            if _is_negative(msg_for_protocol) and state.extra_context in ("none", None):
                msg_for_protocol = ""

            keywords = []
            if state.primary_region == "general":
                region_hits = (state.preferences or {}).get("region_hits", [])
                for hit in region_hits:
                    keywords.extend(_region_keywords(hit))
                if not keywords:
                    # Ensure the synthetic prompt contains enough context to avoid the
                    # "generic greeting" guard in `_handle_diagnosis_v3` and consistently
                    # generate a baseline (foundation) protocol for general wellness.
                    keywords.extend(["general", "wellness", "lymphatic", "support", "swelling"])
            else:
                keywords.extend(_region_keywords(state.primary_region))
            keywords.extend(_context_keywords(state.context_trigger))
            if state.timing:
                keywords.append(state.timing)
            if state.extra_context and state.extra_context != "none":
                msg_for_protocol = f"{msg_for_protocol} {state.extra_context}".strip()
            return f"{' '.join(keywords)} {msg_for_protocol}".strip()
        if inferred_access and profile:
            updated = False
            for need in inferred_access:
                if need not in profile.accessibility_needs:
                    profile.accessibility_needs.append(need)
                    updated = True
            if inferred_wheelchair_arm:
                wheelchair_details = profile.accessibility_details.get("wheelchair", {})
                if wheelchair_details.get("arm_use") != inferred_wheelchair_arm:
                    wheelchair_details["arm_use"] = inferred_wheelchair_arm
                    profile.accessibility_details["wheelchair"] = wheelchair_details
                    updated = True
                if inferred_wheelchair_arm == "no":
                    for need in ["arms", "hands"]:
                        if need not in profile.accessibility_needs:
                            profile.accessibility_needs.append(need)
                            updated = True
            if updated:
                self.update_state(session_id, {"ability_profile": profile})
                state = self.get_state(session_id)

        # Last chance confirmation flow before protocol
        if state.pending_summary_details:
            self.update_state(session_id, {"extra_context": msg, "pending_summary_details": False, "pending_summary_confirmation": False})
            state = self.get_state(session_id)
        
        # ========== Two-Message PDF Generation ==========
        # On the first turn, we show "Building your protocol now..."
        # On the NEXT turn (any user input), we actually generate and return the PDF
        if state.pending_pdf_generation:
            self.update_state(session_id, {"pending_pdf_generation": False})
            state = self.get_state(session_id)
            synthetic_msg = _build_synthetic_msg("")
            _ = self._handle_diagnosis_v3(session_id, synthetic_msg)
            pdf_msg = self._handle_agreement(session_id, "yes")
            return pdf_msg
        
        if state.pending_summary_confirmation:
            if _is_negative(msg):
                # User declined to add extra context - generate PDF immediately
                self.update_state(session_id, {"pending_summary_confirmation": False, "extra_context": "none"})
                state = self.get_state(session_id)
                if state.primary_region and state.context_trigger and state.timing:
                    summary = _build_user_summary_for_protocol(state)
                    synthetic_msg = _build_synthetic_msg("")
                    _ = self._handle_diagnosis_v3(session_id, synthetic_msg)
                    pdf_msg = self._handle_agreement(session_id, "yes")
                    if summary:
                        return f"{summary}\n\n---\n\n{pdf_msg}"
                    return pdf_msg
            elif _is_affirmative(msg) and len(msg.strip().split()) <= 3:
                self.update_state(session_id, {"pending_summary_details": True})
                return "Got it. What should I consider for your protocol?"
            else:
                self.update_state(session_id, {"extra_context": msg, "pending_summary_confirmation": False})
                state = self.get_state(session_id)
                summary = _build_user_summary_for_protocol(state)
                synthetic_msg = _build_synthetic_msg("")
                _ = self._handle_diagnosis_v3(session_id, synthetic_msg)
                pdf_msg = self._handle_agreement(session_id, "yes")
                if summary:
                    return f"{summary}\n\n---\n\n{pdf_msg}"
                return pdf_msg

        # Resolve pending context default question
        if state.pending_context_default:
            if _is_affirmative(msg):
                self.update_state(session_id, {"context_trigger": "daily", "pending_context_default": False})
                state = self.get_state(session_id)
            elif _is_negative(msg):
                self.update_state(session_id, {"pending_context_default": False})
                state = self.get_state(session_id)
            else:
                return ("No problem. If you are unsure, we can treat this as **daily** for now. "
                        "Does that feel accurate?")

        # Update discovery fields if missing
        if not state.primary_region:
            region = interpreted.get("region")
            region_hits = interpreted.get("region_hits") or []
            if not region or region == "unknown":
                region = extract_primary_region(msg_lower)
            if router_ok and (not region or region == "unknown"):
                region = router_interpreted.get("region")
            if llm_ok and (not region or region == "unknown"):
                region = llm_interpreted.get("region")
            if region and region != "unknown":
                updates = {"primary_region": region, "last_question_key": None}
                if region_hits:
                    prefs = dict(state.preferences or {})
                    prefs["region_hits"] = region_hits
                    updates["preferences"] = prefs
                self.update_state(session_id, updates)
                state = self.get_state(session_id)
                slots = dict(state.discovery_slots or {})
                slots["primary_region"] = True
                self.update_state(session_id, {"discovery_slots": slots})
                state = self.get_state(session_id)
        else:
            region_hits = interpreted.get("region_hits") or []
            if region_hits:
                prefs = dict(state.preferences or {})
                prefs["region_hits"] = region_hits
                self.update_state(session_id, {"preferences": prefs})
                state = self.get_state(session_id)

        if not state.context_trigger:
            context = interpreted.get("context")
            logger.info(f"CONTEXT DEBUG: interpreted={context} goal_key={state.goal_key}")

            if not context or context == "unknown":
                context = extract_context_trigger(msg_lower)
                logger.info(f"CONTEXT DEBUG: extract_context_trigger={context}")

            if router_ok and (not context or context == "unknown"):
                context = router_interpreted.get("context")
                logger.info(f"CONTEXT DEBUG: router_interpreted={context}")

            if llm_ok and (not context or context == "unknown"):
                context = llm_interpreted.get("context")
                logger.info(f"CONTEXT DEBUG: llm_interpreted={context}")

            # Guard: don't auto-infer "pregnancy" if the user explicitly chose a different goal
            if context == "pregnancy" and state.goal_key and state.goal_key != "pregnancy":
                logger.info(f"CONTEXT DEBUG: BLOCKING FALSE PREGNANCY. Goal is {state.goal_key}")
                context = None
            
            if context and context != "unknown":
                self.update_state(session_id, {"context_trigger": context, "last_question_key": None})
                state = self.get_state(session_id)
                slots = dict(state.discovery_slots or {})
                slots["context_trigger"] = True
                self.update_state(session_id, {"discovery_slots": slots})
                state = self.get_state(session_id)

        # Permission gate (ask once before discovery questions)
        # IMPLICIT PERMISSION: If user already provided symptom info, skip the permission question
        if not state.discovery_permission_granted:
            # Grant implicit permission if user provided any symptom data proactively
            if state.primary_region or state.context_trigger or state.timing:
                self.update_state(session_id, {"discovery_permission_granted": True, "discovery_permission_asked": True})
            elif not state.discovery_permission_asked:
                self.update_state(session_id, {"discovery_permission_asked": True})
                empathy = _discovery_empathy(msg)
                return (f"{empathy}\n\n"
                        "To build a **targeted lymphatic wellness guide**, would it be okay if I ask **4 to 5 quick questions**?\n\n"
                        "○ Yes, let's go!\n"
                        "○ No thanks")
            # If user answered, handle yes/no
            if _is_affirmative(msg):
                self.update_state(session_id, {"discovery_permission_granted": True})
            elif _is_negative(msg):
                return ("No problem. When you’re ready, tell me the **main concern** you want help with:\n\n"
                        "○ Swelling or heaviness\n"
                        "○ Post-surgery recovery\n"
                        "○ Smoother, firmer-looking skin\n"
                        "○ Exercise recovery\n"
                        "○ Pregnancy comfort\n"
                        "○ General wellness")

        if state.context_trigger and not state.timing:
            timing = interpreted.get("timing") or extract_timing(msg_lower)
            if router_ok and (not timing or timing == "unknown"):
                timing = router_interpreted.get("timing")
            if llm_ok and (not timing or timing == "unknown"):
                timing = llm_interpreted.get("timing")
            if timing and timing != "unknown":
                self.update_state(session_id, {"timing": timing, "last_question_key": None})
                state = self.get_state(session_id)
                slots = dict(state.discovery_slots or {})
                slots["timing"] = True
                self.update_state(session_id, {"discovery_slots": slots})
                state = self.get_state(session_id)

        # Capture constraints early if present
        if router_ok and router_interpreted.get("constraints") and not state.extra_context:
            if not _is_constraint_noise(router_interpreted.get("constraints")):
                self.update_state(session_id, {"extra_context": router_interpreted.get("constraints")})
            state = self.get_state(session_id)
        if llm_ok and llm_interpreted.get("constraints") and not state.extra_context:
            if not _is_constraint_noise(llm_interpreted.get("constraints")):
                self.update_state(session_id, {"extra_context": llm_interpreted.get("constraints")})
            state = self.get_state(session_id)

        # If user provided context before explicit consent, treat it as implicit consent
        if not state.discovery_permission_granted and state.discovery_permission_asked and (state.primary_region or state.context_trigger or state.timing):
            self.update_state(session_id, {"discovery_permission_granted": True})

        if not state.primary_region:
            # Map numeric option-button selections to region values
            _REGION_OPTION_MAP = {
                "1": "legs",      # Legs & feet
                "2": "arms",      # Arms & hands
                "3": "face",      # Face & neck
                "4": "abdomen",   # Abdomen & core
                "5": "general",   # Multiple areas / whole body
            }
            region_from_btn = _REGION_OPTION_MAP.get(msg.strip())
            if region_from_btn:
                self.update_state(session_id, {"primary_region": region_from_btn, "last_question_key": None})
                state = self.get_state(session_id)
                slots = dict(state.discovery_slots or {})
                slots["primary_region"] = True
                self.update_state(session_id, {"discovery_slots": slots})
                state = self.get_state(session_id)

        if not state.primary_region:
            empathy = _discovery_empathy(msg)
            attempts = _get_attempts(state, "region")
            if _is_repeat_frustration(msg) and not interpreted.get("region"):
                self.update_state(session_id, {"primary_region": "general", "last_question_key": None})
                state = self.get_state(session_id)
            elif attempts >= 2:
                self.update_state(session_id, {"primary_region": "general", "last_question_key": None})
                state = self.get_state(session_id)
            else:
                if attempts >= 1 or _is_repeat_frustration(msg) or interpreted.get("uncertain_region") or _is_uncertain(msg):
                    question = ("If you already told me, I may have missed it.\n\n"
                                "○ Legs & feet\n"
                                "○ Arms & hands\n"
                                "○ Face & neck\n"
                                "○ Abdomen & core\n"
                                "○ Multiple areas / whole body")
                else:
                    # FIRST ATTEMPT: If user gave ANY substantive response (3+ words or contains keywords), 
                    # treat it as valid "general" wellness and proceed
                    words = msg.strip().split()
                    has_wellness_intent = any(w in msg_lower for w in ["pregnant", "pregnancy", "healthy", "wellness", "health", "better", "just", "want"])
                    if len(words) >= 3 or has_wellness_intent:
                        # Accept their response as general wellness context
                        self.update_state(session_id, {
                            "primary_region": "general",
                            "context_trigger": "daily",
                            "extra_context": msg,
                            "last_question_key": None
                        })
                        state = self.get_state(session_id)
                    else:
                        goal_key = state.goal_key or "wellness"
                        descriptor = _GOAL_DESCRIPTORS.get(goal_key, "swelling or heaviness")
                        
                        if goal_key == "wellness":
                            question_text = "Where in your body would you like to focus your wellness routine?"
                        else:
                            question_text = f"Where in your body is the {descriptor} most noticeable?"

                        question = (f"{question_text}\n\n"
                                    "○ Legs & feet\n"
                                    "○ Arms & hands\n"
                                    "○ Face & neck\n"
                                    "○ Abdomen & core\n"
                                    "○ Multiple areas / whole body")
                        reason = "That helps me target the right lymphatic pathways."
                        self.update_state(session_id, _record_question(state, "region"))
                        return f"{empathy}\n\n{reason}\n\n{question}"


        if not state.context_trigger:
            # Map numeric option-button selections to context values
            _CONTEXT_OPTION_MAP = {
                "1": "surgery",    # After surgery
                "2": "travel",     # Travel / flights
                "3": "training",   # Workouts / training
                "4": "heat",       # Heat / weather
                "5": "pregnancy",  # Pregnancy
                "6": "daily",      # Daily / ongoing
            }
            context_from_btn = _CONTEXT_OPTION_MAP.get(msg.strip())
            if context_from_btn:
                self.update_state(session_id, {"context_trigger": context_from_btn, "last_question_key": None})
                state = self.get_state(session_id)
                slots = dict(state.discovery_slots or {})
                slots["context_trigger"] = True
                self.update_state(session_id, {"discovery_slots": slots})
                state = self.get_state(session_id)

        if not state.context_trigger:
            empathy = _discovery_empathy(msg)
            attempts = _get_attempts(state, "context")
            if interpreted.get("uncertain_context") or _is_uncertain(msg):
                if attempts >= 1:
                    self.update_state(session_id, {"context_trigger": "daily", "pending_context_default": False, "last_question_key": None})
                    state = self.get_state(session_id)
                else:
                    self.update_state(session_id, {"pending_context_default": True})
                    self.update_state(session_id, _record_question(state, "context"))
                    return ("No problem. If you are unsure, we can treat this as **daily** for now. "
                            "Does that feel accurate?\n\n"
                            "○ Yes, that's fine\n"
                            "○ No, let's try again")
            if not state.context_trigger:
                if attempts >= 1:
                    question = ("If none of these fit, just pick **Daily / ongoing**.\n\n"
                                "○ After surgery\n"
                                "○ Travel / flights\n"
                                "○ Workouts / training\n"
                                "○ Heat / weather\n"
                                "○ Pregnancy\n"
                                "○ Daily / ongoing")
                else:
                    question = ("Did this start after something specific, or is it more of an ongoing thing?\n\n"
                                "○ After surgery\n"
                                "○ Travel / flights\n"
                                "○ Workouts / training\n"
                                "○ Heat / weather\n"
                                "○ Pregnancy\n"
                                "○ Daily / ongoing")
                reason = "The trigger changes which protocol is safest and most effective."
                self.update_state(session_id, _record_question(state, "context"))
                return f"{empathy}\n\n{reason}\n\n{question}"

        if not state.timing:
            # Map numeric option-button selections to timing values
            _TIMING_OPTION_MAP = {
                "1": "morning",    # Morning
                "2": "afternoon",  # Afternoon
                "3": "evening",    # Evening
                "4": "all_day",    # All day / constant
                "5": "on_and_off", # On and off
            }
            timing_from_btn = _TIMING_OPTION_MAP.get(msg.strip())
            if timing_from_btn:
                self.update_state(session_id, {"timing": timing_from_btn, "last_question_key": None})
                state = self.get_state(session_id)
                slots = dict(state.discovery_slots or {})
                slots["timing"] = True
                self.update_state(session_id, {"discovery_slots": slots})
                state = self.get_state(session_id)

        if not state.timing:
            empathy = _discovery_empathy(msg)
            attempts = _get_attempts(state, "timing")
            if attempts >= 2:
                self.update_state(session_id, {"timing": "all_day", "last_question_key": None})
                state = self.get_state(session_id)
            else:
                if attempts >= 1 or _is_repeat_frustration(msg) or interpreted.get("uncertain_timing") or _is_uncertain(msg):
                    question = ("If it varies or feels constant, pick **All day** or **On and off**.\n\n"
                                "○ Morning\n"
                                "○ Afternoon\n"
                                "○ Evening\n"
                                "○ All day / constant\n"
                                "○ On and off")
                else:
                    goal_key = state.goal_key or "wellness"
                    if goal_key == "wellness":
                        question_text = "When would you like to perform your routine for the best results?"
                    else:
                        question_text = "When does it tend to feel worst?"

                    question = (f"{question_text}\n\n"
                                "○ Morning\n"
                                "○ Afternoon\n"
                                "○ Evening\n"
                                "○ All day / constant\n"
                                "○ On and off")
                reason = "Timing helps me sequence your routine for the biggest relief."
                self.update_state(session_id, _record_question(state, "timing"))
                return f"{empathy}\n\n{reason}\n\n{question}"


        # All required fields collected. Generate PDF and return formatted two-part message.
        if state.primary_region and state.context_trigger and state.timing and not state.pending_summary_confirmation:
            summary = _build_user_summary_for_protocol(state)
            
            # Build protocol silently
            synthetic_msg = _build_synthetic_msg("")
            _ = self._handle_diagnosis_v3(session_id, synthetic_msg)
            
            # REFRESH STATE: ensure we have protocol_items from silent build
            state = self.get_state(session_id)
            
            # Generate PDF
            pdf_msg = self._handle_agreement(session_id, "yes")
            
            # Return formatted two-part message
            if summary:
                return f"{summary}\n\n---\n\n{pdf_msg}"
            return pdf_msg

        # All required fields collected -> generate protocol
        synthetic_msg = _build_synthetic_msg(msg)
        return self._handle_diagnosis_v3(session_id, synthetic_msg)

    def _handle_agreement(self, session_id, msg):
        """
        Handle protocol agreement/modification flow.
        Now supports ACTUAL modifications via RefinementEngine.
        """
        msg_lower = msg.lower()
        state = self.get_state(session_id)
        
        # --- Initialize RefinementEngine ---
        refinement_engine = RefinementEngine()
        
        # --- Affirmative Keywords (Final Acceptance) ---
        affirmative_keywords = [
            "yes", "sure", "ok", "okay", "great", "sounds good", "please",
            "protocol", "routine", "generate", "pdf", "send", "perfect", "love it",
            "looks good", "that works", "let's do it", "i'm ready", "ready"
        ]
        
        # --- Modification Keywords (User wants to change something) ---
        modification_keywords = [
            "less", "fewer", "reduce", "shorter", "easier", "simpler",
            "more", "harder", "longer", "intense", "increase",
            "change", "modify", "adjust", "can we", "could we",
            "too much", "too hard", "too long", "not sure", "busy",
            "time", "reps", "sets", "minutes", "days", "dose", "intensity", "timing"
        ]
        
        # --- Check for pure affirmative (no modification words) ---
        has_affirmative = any(w in msg_lower for w in affirmative_keywords)
        has_modification = any(w in msg_lower for w in modification_keywords)

        # Explicit acceptance phrases that include modification keywords
        explicit_acceptance = bool(re.search(
            r"\b(no (change|changes|adjustment|adjustments|modification|mods|tweaks)|no need to change|keep it as is|"
            r"fine as is|looks good|all set|no changes needed|no adjustments needed)\b",
            msg_lower
        ))
        if explicit_acceptance:
            has_affirmative = True
            has_modification = False
        
        # If pure affirmative -> generate PDF
        if has_affirmative and not has_modification:
            protocol_items = state.protocol_items or []
            
            # Emergency fallback: if empty, try to populate from Foundation
            if not protocol_items:
                logger.warning(f"Empty protocol_items for {session_id}. Injecting Foundation fallback.")
                from services.clinical_library import CLINICAL_PROTOCOLS
                foundation = CLINICAL_PROTOCOLS.get("foundation", {})
                raw_items = foundation.get("items", [])
                for it in raw_items:
                    protocol_items.append({"action": it.get("name"), "details": it.get("dose") or it.get("instruction")})
                self.update_state(session_id, {"protocol_items": protocol_items, "agreed_protocol": ["Whole-Body Foundation Stack"]})
                state = self.get_state(session_id)

            # Goal-aware title
            title = self._GOAL_TITLES.get(state.goal_key, state.agreed_protocol[0] if state.agreed_protocol else "Your Lymphatic Wellness Focus")
            user_name = state.user_name or "Valued Client"

            # Run coherence validator before PDF generation
            title, protocol_items, coherence_warnings = self._validate_and_fix_coherence(
                session_id, protocol_items, title)

            pdf_path = None
            try:
                pdf_path = self.protocol_gen.generate_pdf(
                    conversation_id=session_id,
                    user_name=user_name,
                    root_cause=title,
                    daily_items=protocol_items,
                    weekly_items=[],
                    email=state.user_email,
                    profile={
                        "goal_key": state.goal_key or "wellness",
                        "primary_region": state.primary_region or "general",
                        "context_trigger": state.context_trigger or "",
                        "health_status": state.ability_profile.tier if state.ability_profile else "average",
                        "exercise_tolerance": state.ability_profile.exercise_tolerance if state.ability_profile else None,
                        "pregnancy_trimester": state.ability_profile.pregnancy_trimester if state.ability_profile else None,
                        "mobility": state.ability_profile.accessibility_needs if state.ability_profile else [],
                        "accessibility_details": state.ability_profile.accessibility_details if state.ability_profile else {},
                        "all_health_tiers": state.ability_profile.all_health_tiers if state.ability_profile else [],
                    },
                    citations=[url for item in protocol_items for url in (item.get("urls") or [])]
                )
            except Exception:
                pdf_path = None
            pdf_url = None
            if pdf_path:
                filename = os.path.basename(pdf_path)
                pdf_url = f"{BACKEND_URL}/static/protocols/{filename}"
            self.update_state(session_id, {"stage": "fork"})
            
            # Build protocol summary for CRM and returning user context
            protocol_summary = None
            if protocol_items:
                item_names = [item.get("action", "Unknown") for item in protocol_items[:3]]
                if len(protocol_items) > 3:
                    protocol_summary = f"{title} protocol: {', '.join(item_names)} and {len(protocol_items) - 3} more exercises"
                else:
                    protocol_summary = f"{title} protocol: {', '.join(item_names)}"
            else:
                protocol_summary = f"{title} protocol"
            
            # Save to CRM for smart returning user context
            if self.crm and pdf_url and protocol_summary:
                try:
                    self.crm.update_conversation_protocol(session_id, pdf_url, protocol_summary)
                except Exception as e:
                    logger.error(f"CRM Protocol Update Failed: {e}")
            
            logger.info(f"PDF GENERATION DEBUG: pdf_path={pdf_path} pdf_url={pdf_url} user_name={user_name}")

            if pdf_url:
                return ("Fantastic! Your personalized protocol PDF is ready. \n\n"
                        f"[Download your protocol]({pdf_url})\n\n"
                        f"What would you like to do next?\n\n"
                        f"{FORK_OPTIONS}")
            return ("Fantastic! I've prepared your personalized protocol.\n\n"
                    f"What would you like to do next?\n\n"
                    f"{FORK_OPTIONS}")
        
        # --- Handle Modification Request ---
        if has_modification:
            # Load or create ActiveProtocol
            active_protocol = None
            if state.active_protocol_data:
                try:
                    active_protocol = ActiveProtocol.from_dict(state.active_protocol_data)
                except Exception:
                    active_protocol = None
            
            # If no active protocol, create from library based on current context
            if not active_protocol:
                # Determine protocol key from context
                protocol_key = "foundation"
                if state.primary_region:
                    region = state.primary_region.lower()
                    if any(w in region for w in ["leg", "ankle", "foot", "feet", "calf"]):
                        protocol_key = "legs"
                    elif any(w in region for w in ["arm", "hand", "finger"]):
                        protocol_key = "arms"
                    elif any(w in region for w in ["neck", "face", "head"]):
                        protocol_key = "neck"
                if state.context_trigger and any(w in state.context_trigger.lower() for w in ["surgery", "post-op", "lipo"]):
                    protocol_key = "post_op"
                
                active_protocol = create_active_protocol_from_library(protocol_key, CLINICAL_PROTOCOLS)
            
            if active_protocol:
                # Apply modification
                modified_protocol, change_explanation = refinement_engine.apply_modification(
                    active_protocol, msg
                )
                
                # Save updated protocol to state
                self.update_state(session_id, {
                    "active_protocol_data": modified_protocol.to_dict(),
                    "refinement_count": state.refinement_count + 1
                })
                
                # Re-render the updated protocol
                updated_display = refinement_engine.render_protocol(modified_protocol)
                
                return (f"{change_explanation}\n\n"
                        f"{updated_display}\n\n"
                        "Does this feel more realistic?\n\n"
                        "○ Yes, looks good!\n"
                        "○ I'd like to adjust more")
            else:
                # Fallback if we couldn't load protocol
                self.update_state(session_id, {"refinement_count": state.refinement_count + 1})
                return ("Understood. What specifically would you like to adjust?\n\n"
                        "○ Make it shorter\n"
                        "○ Make it easier\n"
                        "○ Make it harder")
        
        # --- Handle Questions ---
        if "?" in msg:
            return ("Great question! What would you like me to clarify?\n\n"
                    "○ Explain an exercise\n"
                    "○ Why does this help?\n"
                    "○ Adjust the routine")
        
        # --- Fallback (prompt for specific modification or acceptance) ---
        return ("I want to make sure this works for you. "
                "Would you like to adjust **time**, **intensity**, or **frequency**? "
                "Or if it looks good, just click **Looks good** to finalize!\n\n"
                "○ Yes, looks good!\n"
                "○ Make it shorter\n"
                "○ Make it easier\n"
                "○ Make it harder")

    def _handle_fork(self, session_id, msg):
        """Handle post-PDF fork: route to products, consultation, or gracefully end."""
        msg_lower = (msg or "").lower()
        state = self.get_state(session_id)
        
        # "I'm all set" / exit
        exit_keywords = ["all set", "thank", "bye", "done", "no", "nothing", "that's it"]
        if any(w in msg_lower for w in exit_keywords):
            self.update_state(session_id, {"stage": "complete"})
            return ("It was wonderful helping you today! Your protocol is saved and ready to download anytime.\n\n"
                    "Explore more at [elastiqueathletics.com](https://www.elastiqueathletics.com)! 😊")
        
        # User wants to see products
        product_keywords = ["clothing", "clothes", "garment", "compression", "wear", "legging", 
                           "product", "shop", "buy", "browse", "show me"]
        if any(w in msg_lower for w in product_keywords) or msg.strip() == "1":
            # --- PATH-AWARE PRODUCT RECOMMENDATIONS ---
            # Translate state fields to PATH_TO_PRODUCTS keys
            _REGION_TO_AREA = {
                "legs": "legs", "arms": "arms", "face": "face",
                "abdomen": "tummy", "general": "all", "neck": "face",
            }
            goal_key = state.goal_key or "wellness"
            q2_area = _REGION_TO_AREA.get(state.primary_region or "general", "all")
            q3_context = state.context_trigger or ""
            
            path_result = get_products_for_path(goal_key, q2_area, q3_context)
            primary_key = path_result.get("primary")
            complement_key = path_result.get("complement")
            
            primary = PRODUCT_CATALOG.get(primary_key) if primary_key else None
            complement = PRODUCT_CATALOG.get(complement_key) if complement_key else None
            
            self.update_state(session_id, {"stage": "complete"})
            
            # Build product recommendation message
            parts = ["Great choice! Based on your wellness goals, here are my top picks:\n"]
            
            if primary:
                parts.append(f"**Primary: {primary['name']}**")
                parts.append(f"> *{primary['mechanism']}*")
                parts.append(f"[View Product]({primary['url']})\n")
            
            if complement:
                parts.append(f"**Also pairs well: {complement['name']}**")
                parts.append(f"> *{complement['mechanism']}*")
                parts.append(f"[View Product]({complement['url']})\n")
            
            if not primary and not complement:
                parts.append("You can explore the full collection at ")
                parts.append("[elastiqueathletics.com](https://www.elastiqueathletics.com)")
            
            parts.append("\nExplore more at [elastiqueathletics.com](https://www.elastiqueathletics.com)! 😊")
            return "\n".join(parts)
        
        # User wants a consultation
        consult_keywords = ["consult", "appointment", "book", "schedule", "call", "talk", "speak"]
        if any(w in msg_lower for w in consult_keywords) or msg.strip() == "2":
            self.update_state(session_id, {"stage": "complete"})
            return ("I'd love to connect you with our team!\n\n"
                    "You can book a consultation at "
                    "[elastiqueathletics.com/pages/contact-us](https://www.elastiqueathletics.com/pages/contact-us)\n\n"
                    "Explore more at [elastiqueathletics.com](https://www.elastiqueathletics.com)! 😊")

        
        # Any other response → offer final options before exit
        return ("It was great chatting with you! Your protocol is saved and ready to download anytime.\n\n"
                "Is there anything else I can help with?\n\n"
                f"{FORK_OPTIONS}")
