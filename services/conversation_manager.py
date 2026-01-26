from typing import Dict, List, Optional
import os
import random
import re
try:
    import spacy
except Exception:
    spacy = None
from services.clinical_library import CLINICAL_PROTOCOLS 
from services.product_catalog import PRODUCT_CATALOG 
from services.crm_service import CRMService 
from services.safety_service import SafetyService
from services.schemas import UserSessionState
from services.redaction import redact_phi
from services.research_library import ResearchLibrary
from services.response_interpreter import ResponseInterpreter
from services.decision_router import DecisionRouter
from services.protocol_generator import ProtocolGenerator
import logging

# --- Global NLP Config ---
try:
    nlp = spacy.load("en_core_web_sm") if spacy else None
except Exception:
    nlp = None

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TITLE_PREFIXES = {"mr", "mrs", "ms", "dr", "prof", "sir", "madam"}
INVALID_NAME_TOKENS = {"yes", "no", "sure", "ok", "okay", "hello", "hi", "hey", "yo", "is", "name"}
INVALID_NAME_VERBS = {"having", "feeling", "experiencing", "dealing", "getting", "hurting", "swelling", "pain", "aches", "aching"}

def _strip_title(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return ""
    first = parts[0].lower().strip(".,")
    if first in TITLE_PREFIXES and len(parts) > 1:
        parts = parts[1:]
    return parts[0].strip(".,") if parts else ""

def extract_name(text: str) -> str:
    """
    Extracts a first name from a string.
    Supports: "Call me Jim", "I am Jim", "Name: Jim", "Jim jim@email.com".
    """
    # 1. Regex Pattern Matching (Priority)
    match = re.search(r"(?:name is|i am|i'm|im|call me|it's|its|this is|name[:\s]+)\s+([A-Z][a-zA-Z'-]+)", text, re.IGNORECASE)
    if match:
        name = _strip_title(match.group(1))
        if name and name.lower() not in INVALID_NAME_TOKENS and name.lower() not in INVALID_NAME_VERBS:
            return name

    # 2. spaCy NER (if available)
    if nlp:
        try:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    name = _strip_title(ent.text)
                    if name and name.lower() not in INVALID_NAME_TOKENS and name.lower() not in INVALID_NAME_VERBS:
                        return name
        except Exception:
            pass

    # 3. Fallback: short message heuristic
    words = [w.strip(".,!?;") for w in text.strip().split() if w.strip(".,!?;")]
    if len(words) <= 2:
        candidate = _strip_title(words[0])
        if candidate and candidate.lower() not in INVALID_NAME_TOKENS and candidate.lower() not in INVALID_NAME_VERBS:
            return candidate
    return None

def is_valid_email(email: str) -> bool:
    return bool(email and EMAIL_REGEX.fullmatch(email))

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
    local_part = email.split("@")[0].lower() if email else None
    if email and name:
        if local_part and name.lower() in local_part:
            name = None

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
                if candidate and candidate.lower() not in INVALID_NAME_TOKENS:
                    name = candidate
                break

    # If still missing, try token after email (e.g., "name is x@email.com Chris")
    if email and not name:
        tokens = [t.strip(".,!?;") for t in text.split()]
        for i, tok in enumerate(tokens):
            if email in tok and i + 1 < len(tokens):
                candidate = _strip_title(tokens[i + 1])
                if candidate and candidate.isalpha() and candidate.lower() not in INVALID_NAME_TOKENS:
                    name = candidate
                break

    # If still missing, use first reasonable word as name (e.g., "Mike here, mike@test.com")
    if email and not name:
        for tok in text.split():
            candidate = _strip_title(tok)
            if candidate and candidate.isalpha() and candidate.lower() not in INVALID_NAME_TOKENS:
                name = candidate
                break

    return {"name": name, "email": email}

def detect_goal(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if any(k in t for k in ["consult", "consultation", "specialist", "1:1", "one-on-one", "schedule", "appointment"]):
        return "consult"
    if any(k in t for k in ["shop", "buy", "purchase", "products", "leggings", "bra", "tank", "clothing"]):
        return "shop"
    if any(k in t for k in ["protocol", "routine", "help", "support", "wellness", "swelling", "pain", "recovery"]):
        return "protocol"
    return None

def extract_primary_region(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if any(w in t for w in ["all over", "everywhere", "whole body", "entire body", "general", "overall", "full body"]):
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
    if any(w in t for w in ["daily", "every day", "all day", "always", "all the time", "ongoing", "standing", "sitting", "desk", "work", "job", "long day", "long shift", "after work", "after a long day"]):
        return "daily"
    return None

def extract_timing(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if any(w in t for w in ["i dont know", "i don't know", "idk", "not sure", "unsure", "no idea", "unknown"]):
        return "variable"
    if any(w in t for w in ["all day", "all day long", "all the time", "anytime", "off and on", "throughout", "all of them", "doesnt matter", "doesn't matter", "no difference", "same", "the same", "always", "daily", "every day", "constant", "24 7", "24-7", "24/7"]):
        return "all_day"
    if any(w in t for w in ["morning", "am", "wake up", "waking", "first thing"]):
        return "morning"
    if any(w in t for w in ["afternoon", "midday", "lunch", "after lunch"]):
        return "afternoon"
    if any(w in t for w in ["evening", "night", "pm", "late in the day", "end of day", "after dinner", "sunset", "bedtime", "after work"]):
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
    return any(w in t for w in ["no", "not now", "don't", "do not", "prefer not", "skip"])

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
    text = re.sub(r"https?://\S+", _protect_url, text)
    text = text.replace("—", ". ").replace("–", ". ")
    text = text.replace(" - ", ". ")
    text = re.sub(r"(\d)\s*-\s*(\d)", r"\1 to \2", text)
    text = re.sub(r"(?<=\w)-(?=\w)", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    for key, url in urls.items():
        text = text.replace(key, url)
    return text

def _build_user_summary(state: Optional[UserSessionState]) -> Optional[str]:
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
    summary = "Here is what I heard. " + " ".join(sentences)
    return summary

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

    async def process_turn(self, session_id: str, user_msg: str, user_email: Optional[str] = None) -> str:
        # 0A. Universal Safety Rail (Hard Refusal)
        safety_refusal = SafetyService.check_emergency(user_msg)
        if safety_refusal:
             return safety_refusal

        # Telemetry
        if self.analytics:
             self.analytics.track_message(session_id, "user", user_msg)

        state = self.get_state(session_id)
        msg_lower = user_msg.lower()
        
        # 0B. Handle System Start
        if user_msg == "Event: Start":
            if self.analytics: self.analytics.track_session_start(session_id, {"email_provided": bool(user_email)})
            
            # Scenario 1: Active Session (Same Session ID)
            if state.user_name:
                self.crm.log_interaction(session_id, "System", "Welcome Back trigger")
                response = (f"Welcome back, {state.user_name}! "
                            "What are you looking to accomplish today? "
                            "**a lymphatic wellness protocol**, **shopping**, or **a 1:1 consult**?")
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

                        if intent:
                            response = (f"Welcome back, {crm_name}! Last time we were working on your **{intent}**. "
                                        "What are you looking to accomplish today? "
                                        "**a lymphatic wellness protocol**, **shopping**, or **a 1:1 consult**?")
                            return await self._finalize_response(session_id, user_msg, response)
                    
                    # No specific protocol yet? Ask generic but personalized.
                    response = (f"Welcome back, {crm_name}! "
                                "What are you looking to accomplish today? "
                                "**a lymphatic wellness protocol**, **shopping**, or **a 1:1 consult**?")
                    return await self._finalize_response(session_id, user_msg, response)
                
                # Known Email but NO Name in CRM? -> Identity Capture (Strict)
                self.update_state(session_id, {"stage": "identity_capture", "user_email": user_email})
                return f"Welcome back! I see you're logged in as {user_email}, but I don't have your first name on file yet. **What should I call you?**"
            
            else:
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
                    return ("Thanks! That doesn't look like a valid email address. "
                            "I need a **valid email** to remember your needs and build your **custom lymphatic wellness protocol**. "
                            "What's the best email to use?")
                
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
                
                # We have BOTH Name and Email. Proceed.
                # Persist
                self.update_state(session_id, {"stage": "goal_capture", "user_email": email_part, "user_name": name_part})
                if self.crm:
                    self.crm.create_or_update_contact(email=email_part, first_name=name_part)
                
                # If they already described symptoms, go straight to discovery without jumping into protocol
                is_diagnosis_keyword = any(w in user_msg.lower() for w in ["swelling", "ankle", "leg", "surgery", "post op", "post-op", "lipo", "recovery", "protocol", "product", "leggings", "hurt", "pain"])
                if is_diagnosis_keyword:
                    self.update_state(session_id, {"goal": "protocol", "stage": "discovery"})
                    response = f"Thanks {name_part}! I've saved your profile. {self._handle_discovery(session_id, user_msg)}"
                    return await self._finalize_response(session_id, user_msg, response)

                response = (f"Thanks {name_part}! I've saved your profile. "
                            "What are you looking to accomplish today? "
                            "**a lymphatic wellness protocol**, **shopping**, or **a 1:1 consult**?")
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
                    # Success! We have both.
                    self.update_state(session_id, {"stage": "goal_capture", "user_name": parsed_name})
                    if self.crm:
                         self.crm.create_or_update_contact(email=state.user_email, first_name=parsed_name)
                    
                    response = (f"Thanks {parsed_name}! I've saved your profile. "
                                "What are you looking to accomplish today? "
                                "**a lymphatic wellness protocol**, **shopping**, or **a 1:1 consult**?")
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
                response = (f"I have your email as **{state.user_email}**. "
                            "What are you looking to accomplish today? "
                            "A lymphatic wellness protocol, shopping, or a 1:1 consult?")
                return await self._finalize_response(session_id, user_msg, response)
            goal = detect_goal(user_msg)
            if not goal:
                symptom_keywords = ["swelling", "swollen", "ankle", "leg", "legs", "pain", "hurt", "ache", "aching", "heavy", "edema", "puffy", "cankle"]
                if any(w in msg_lower for w in symptom_keywords):
                    self.update_state(session_id, {"goal": "protocol", "stage": "discovery"})
                    response = self._handle_discovery(session_id, user_msg)
                    return await self._finalize_response(session_id, user_msg, response)
                if _is_uncertain(user_msg):
                    self.update_state(session_id, {"pending_goal_default": True})
                    response = "No problem. Most people start with a lymphatic wellness protocol. Does that sound right?"
                    return await self._finalize_response(session_id, user_msg, response)
                response = ("What are you looking to accomplish today? "
                            "**a lymphatic wellness protocol**, **shopping**, or **a 1:1 consult**?")
                return await self._finalize_response(session_id, user_msg, response)

            self.update_state(session_id, {"goal": goal, "stage": "discovery"})

            if goal == "consult":
                response = ("Wonderful. To get you set up, may I have your **best phone number** "
                            "for our specialist to call?")
                return await self._finalize_response(session_id, user_msg, response)

            # Protocol or Shopping intent flows into discovery
            response = self._handle_discovery(session_id, user_msg)
            return await self._finalize_response(session_id, user_msg, response)

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
            
        response = "I'm listening. Tell me more about what you're feeling in your body today."
        return await self._finalize_response(session_id, user_msg, response)

    async def _finalize_response(self, session_id: str, user_msg: str, response: str) -> str:
        if not self.llm_rewriter:
            return _sanitize_no_dashes(response)
        state = self.get_state(session_id)
        rewritten = await self.llm_rewriter.rewrite(user_msg, response, state)
        return _sanitize_no_dashes(rewritten)

    def _handle_diagnosis_v3(self, session_id, msg):
        """
        V3 Implementation of 'Empathy Sandwich'
        Layer 1: Validation (Visual/Text)
        Layer 2: Education (Mechanism)
        Layer 3: Prescription (Linked Protocol)
        """
        msg_lower = msg.lower()
        
        # --- A. Context Detection ---
        is_photo = "photo" in msg_lower or "analyzing tissue" in msg_lower or "jpg" in msg_lower
        
        # Detect Body Part / Issue
        issue_type = "foundation" # Default
        if any(w in msg_lower for w in ["surgery", "post-op", "post_op", "postop", "lipo", "recovery"]):
            issue_type = "post_op"
        elif any(w in msg_lower for w in ["leg", "ankle", "foot", "feet", "calf", "calves", "cankle"]):
            issue_type = "legs"
        elif any(w in msg_lower for w in ["arm", "hand", "finger", "elbow"]):
            issue_type = "arms"
        elif any(w in msg_lower for w in ["neck", "face", "jaw"]):
            issue_type = "neck"
            
        elif any(w in msg_lower for w in ["neck", "face", "jaw"]):
            issue_type = "neck"
            
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
            else:
                 # Foundation / Default
                intro = "Thanks for sharing. It sounds like you want to support your body's natural flow, which is the foundation of energy and health."

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
        else:
             bridge_core = ("\n\n**Here is the science:**\n"
                            "The lymphatic system is your body's sewage treatment plant. Without a pump, it needs specific targeted movements "
                            "(like deep breathing) to create the pressure changes that move fluid.")

        summary = _build_user_summary(state)
        if summary and not state.extra_context:
            bridge = f"\n\n{summary} If I missed anything, tell me."
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
        # Improved Formatting for readability
        prescription = ["\n\n**Here is a Science Backed Routine tailored for you:**"]
        
        for item in selected_protocol['items']:
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
            dose = item.get("dose")
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
        product = PRODUCT_CATALOG.get(issue_type)
        if product:
            prescription.append(f"\n\n**Supportive Tool:**")
            prescription.append(f"To make this habit easier, many clients use the **{product['name']}**.")
            prescription.append(f"> *{product['mechanism']}*")
            prescription.append(f"[Show Me]({product['url']})")

        # --- F. Closing ---
        closing = "\n\nDoes this routine feel manageable, or would you like any changes or questions before we finalize it?"
        
        # Combine
        full_response = intro + bridge + "".join(prescription) + closing
        
        # Update State
        protocol_items = []
        for item in selected_protocol.get("items", []):
            action = item.get("name")
            details = item.get("dose") or item.get("instruction")
            if action and details:
                protocol_items.append({"action": action, "details": details})
        self.update_state(session_id, {"stage": "agreement", "agreed_protocol": [selected_protocol['title']], "protocol_items": protocol_items})
        
        return full_response

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

        # Last chance confirmation flow before protocol
        if state.pending_summary_details:
            self.update_state(session_id, {"extra_context": msg, "pending_summary_details": False, "pending_summary_confirmation": False})
            state = self.get_state(session_id)
        elif state.pending_summary_confirmation:
            if _is_negative(msg):
                self.update_state(session_id, {"pending_summary_confirmation": False})
                state = self.get_state(session_id)
            elif _is_affirmative(msg) and len(msg.strip().split()) <= 3:
                self.update_state(session_id, {"pending_summary_details": True})
                return "Got it. What should I consider for your protocol?"
            else:
                self.update_state(session_id, {"extra_context": msg, "pending_summary_confirmation": False})
                state = self.get_state(session_id)

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
            region = interpreted.get("region") or extract_primary_region(msg_lower)
            if router_ok and (not region or region == "unknown"):
                region = router_interpreted.get("region")
            if llm_ok and (not region or region == "unknown"):
                region = llm_interpreted.get("region")
            if region and region != "unknown":
                self.update_state(session_id, {"primary_region": region, "last_question_key": None})
                state = self.get_state(session_id)

        if not state.context_trigger:
            context = interpreted.get("context") or extract_context_trigger(msg_lower)
            if router_ok and (not context or context == "unknown"):
                context = router_interpreted.get("context")
            if llm_ok and (not context or context == "unknown"):
                context = llm_interpreted.get("context")
            if context and context != "unknown":
                self.update_state(session_id, {"context_trigger": context, "last_question_key": None})
                state = self.get_state(session_id)

        # Permission gate (ask once before discovery questions)
        if not state.discovery_permission_granted:
            if not state.discovery_permission_asked:
                self.update_state(session_id, {"discovery_permission_asked": True})
                empathy = _discovery_empathy(msg)
                return (f"{empathy}\n\n"
                        "To build a **targeted lymphatic wellness guide**, would it be okay if I ask **4 to 5 quick questions**?")
            # If user answered, handle yes/no
            if _is_affirmative(msg):
                self.update_state(session_id, {"discovery_permission_granted": True})
            elif _is_negative(msg):
                return ("No problem. When you’re ready, tell me the **main area** you want help with and your **primary goal**, "
                        "and I’ll keep it brief.")

        if state.context_trigger and not state.timing:
            timing = interpreted.get("timing") or extract_timing(msg_lower)
            if router_ok and (not timing or timing == "unknown"):
                timing = router_interpreted.get("timing")
            if llm_ok and (not timing or timing == "unknown"):
                timing = llm_interpreted.get("timing")
            if timing and timing != "unknown":
                self.update_state(session_id, {"timing": timing, "last_question_key": None})
                state = self.get_state(session_id)

        # Capture constraints early if present
        if router_ok and router_interpreted.get("constraints") and not state.extra_context:
            self.update_state(session_id, {"extra_context": router_interpreted.get("constraints")})
            state = self.get_state(session_id)
        if llm_ok and llm_interpreted.get("constraints") and not state.extra_context:
            self.update_state(session_id, {"extra_context": llm_interpreted.get("constraints")})
            state = self.get_state(session_id)

        # If user provided context before explicit consent, treat it as implicit consent
        if not state.discovery_permission_granted and state.discovery_permission_asked and (state.primary_region or state.context_trigger or state.timing):
            self.update_state(session_id, {"discovery_permission_granted": True})

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
                    question = ("If you already told me, I may have missed it. "
                                "You can say **legs and feet**, **arms and hands**, **face and neck**, "
                                "**abdomen and core**, or **multiple areas**.")
                else:
                    question = "Where in your body is the swelling or heaviness most noticeable?"
                reason = "That helps me target the right lymphatic pathways."
                self.update_state(session_id, _record_question(state, "region"))
                return f"{empathy}\n\n{reason}\n\n{question}"

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
                            "Does that feel accurate?")
            if not state.context_trigger:
                if attempts >= 1:
                    question = ("If none of these fit, you can say **daily** and we will keep it simple. "
                                "Which sounds closest: **surgery**, **travel**, **workouts**, **heat**, **pregnancy**, "
                                "or **daily**?")
                else:
                    question = ("Did this start after **surgery**, **travel**, **workouts**, **heat**, **pregnancy**, "
                                "or is it more of a **daily** issue?")
                reason = "The trigger changes which protocol is safest and most effective."
                self.update_state(session_id, _record_question(state, "context"))
                return f"{empathy}\n\n{reason}\n\n{question}"

        if not state.timing:
            empathy = _discovery_empathy(msg)
            attempts = _get_attempts(state, "timing")
            if attempts >= 2:
                self.update_state(session_id, {"timing": "all_day", "last_question_key": None})
                state = self.get_state(session_id)
            else:
                if attempts >= 1 or _is_repeat_frustration(msg) or interpreted.get("uncertain_timing") or _is_uncertain(msg):
                    question = ("If it varies or feels constant, you can say **all day** or **on and off**. "
                                "Otherwise, which is most true, **morning**, **afternoon**, or **evening**?")
                else:
                    question = "When does it feel worst, **morning**, **afternoon**, or **evening**?"
                reason = "Timing helps me sequence your routine for the biggest relief."
                self.update_state(session_id, _record_question(state, "timing"))
                return f"{empathy}\n\n{reason}\n\n{question}"

        # All required fields collected. Offer final confirmation once.
        if state.primary_region and state.context_trigger and state.timing and not state.pending_summary_confirmation and not state.extra_context:
            self.update_state(session_id, {"pending_summary_confirmation": True})
            summary = _build_user_summary(state)
            if summary:
                return f"{summary} Before I build your protocol, is there anything you want me to consider like injuries, schedule, or constraints?"
            return "Before I build your protocol, is there anything you want me to consider like injuries, schedule, or constraints?"

        # All required fields collected -> generate protocol
        keywords = []
        keywords.extend(_region_keywords(state.primary_region))
        keywords.extend(_context_keywords(state.context_trigger))
        if state.timing:
            keywords.append(state.timing)
        if state.extra_context:
            msg = f"{msg} {state.extra_context}"
        synthetic_msg = f"{' '.join(keywords)} {msg}".strip()
        return self._handle_diagnosis_v3(session_id, synthetic_msg)

    def _handle_agreement(self, session_id, msg):
        msg_lower = msg.lower()
        affirmative_keywords = [
            "yes", "sure", "ok", "okay", "great", "sounds good", "please",
            "protocol", "routine", "generate", "pdf", "send"
        ]
        router = self.decision_router.interpret_agreement(msg) if self.decision_router else {}
        router_conf = (router or {}).get("confidence", "low")
        router_decision = (router or {}).get("decision")
        router_constraints = (router or {}).get("constraints")

        if router_conf in ("medium", "high") and router_constraints:
            self.update_state(session_id, {"extra_context": router_constraints})

        if router_conf in ("medium", "high") and router_decision in ("modify", "unsure", "question", "decline"):
            self.update_state(session_id, {"refinement_count": self.get_state(session_id).refinement_count + 1})
            if router_decision == "question":
                return ("Great question. What part would you like clarified or adjusted so it feels realistic for you?")
            return ("Understood. What would you like to adjust in the routine, intensity, or timing? "
                    "I can tailor it to fit your day.")

        if any(w in msg_lower for w in affirmative_keywords):
            state = self.get_state(session_id)
            protocol_items = state.protocol_items or []
            title = state.agreed_protocol[0] if state.agreed_protocol else "Your Lymphatic Wellness Focus"
            user_name = state.user_name or "Valued Client"
            pdf_path = None
            try:
                pdf_path = self.protocol_gen.generate_pdf(
                    conversation_id=session_id,
                    user_name=user_name,
                    root_cause=title,
                    daily_items=protocol_items,
                    weekly_items=[],
                    email=state.user_email
                )
            except Exception:
                pdf_path = None
            pdf_url = None
            if pdf_path:
                filename = os.path.basename(pdf_path)
                pdf_url = f"/static/protocols/{filename}"
            self.update_state(session_id, {"stage": "fork"})
            if pdf_url:
                return ("Fantastic. Your personalized protocol PDF is ready.\n\n"
                        f"[Download your protocol]({pdf_url})\n\n"
                        "Would you like to see **Clinical Garments** that support this protocol or schedule a **Consultation**?")
            return ("Fantastic. I am preparing your personalized protocol now.\n\n"
                    "Would you like to see **Clinical Garments** that support this protocol or schedule a **Consultation**?")
        
        # Handle objections or modification requests and stay in agreement
        if any(w in msg_lower for w in ["no", "cant", "can't", "hard", "difficult", "change", "modify", "adjust", "too much", "too hard", "too long", "not sure", "unsure"]):
            self.update_state(session_id, {"refinement_count": self.get_state(session_id).refinement_count + 1})
            return ("Understood. What would you like to adjust in the routine, intensity, or timing? "
                    "I can tailor it to fit your day.")
        
        if "?" in msg:
            return ("Great question. What part would you like clarified or adjusted so it feels realistic for you?")

        # Fallback keeps the agreement loop
        return ("Thanks for sharing. What would make this routine feel doable for you so we can lock it in?")

    def _handle_fork(self, session_id, msg):
        return "Would you prefer to look at **Clothing** options or a **Consultation**?"
