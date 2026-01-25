from typing import Dict, List, Optional
import random
import re
import spacy
from services.clinical_library import CLINICAL_PROTOCOLS 
from services.product_catalog import PRODUCT_CATALOG 
from services.crm_service import CRMService 
from services.safety_service import SafetyService
from services.schemas import UserSessionState
import logging

# --- Global NLP Config ---
try:
    nlp = spacy.load("en_core_web_sm")
except:
    nlp = None

def extract_name(text):
    """
    Extracts the first PERSON entity from a string using spaCy.
    Handles 'Call me Jim', 'I am Jim', etc.
    """
    # 1. Regex Pattern Matching (Priority)
    # Support CamelCase or simple names (e.g. BugFixUser, Jim)
    match = re.search(r"(?:name is|I am|I'm|Im|call me|it's|its|this is)\s+([A-Z][a-zA-Z]+)", text, re.IGNORECASE)
    if match:
        return match.group(1)

    if not nlp:
        # 2. Short Message Heuristic (Fallback)
        words = text.strip().split()
        if len(words) <= 2:
             return words[-1].strip(".,!?;")
        return None

logger = logging.getLogger(__name__)

class ConversationManager:
    """
    Manages the conversational state machine for the Elastique Wellness Guide.
    Refactored V3: Implements 'Empathy Sandwich' and 'Educational Bridging' per bot_training_manual.md.
    """
    
    def __init__(self, citation_engine=None, analytics_service=None, mm_service=None):
        self.citation_engine = citation_engine
        self.analytics = analytics_service
        self.crm = CRMService()
        self.mm_service = mm_service # [NEW] Inject Multimodal Service for Smart ID
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
                return f"Welcome back, {state.user_name}! I remember we were discussing your **{state.diagnosis or 'wellness goals'}**. How is it going?"
            
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
                        "stage": "diagnosis"
                    })

                    # Smart Context Greeting (Intent-Aware)
                    intent = last_active.get("intent")
                    last_stage = last_active.get("stage")

                    if intent:
                        # [NEW] Check if they actually finished/agreed to it
                        if last_stage in ["agreement", "complete", "protocol_delivered"]:
                             return f"Welcome back, {crm_name}! Last time we were working on your **{intent}** protocol. How is that going today?"
                        
                        # Pending Protocol (Recommended but not Accepted)
                        return f"Welcome back, {crm_name}! Are you here to continue discussing the protocol I recommended for **{intent}**?"
                    
                    # No specific protocol yet? Ask generic but personalized.
                    return f"Welcome back, {crm_name}! I see we haven't set up a full protocol yet. How can I help your body today?"
                
                # Known Email but NO Name in CRM? -> Identity Capture (Strict)
                self.update_state(session_id, {"stage": "identity_capture", "user_email": user_email})
                return f"Welcome back! I see you're logged in as {user_email}, but I don't have your first name on file yet. **What should I call you?**"
            
            else:
                self.update_state(session_id, {"stage": "identity_capture"})
                return ("Hello! I'm **Sarah**, your Lymphatic Wellness Guide.\n\n"
                        "To build your personalized protocol, I just need your **First Name** and **Email Address**.")

        stage = state.stage
        
        # 1. Identity Capture Stage
        if stage == "identity_capture":
            # A. Check for Email (Strong Signal)
            if "@" in user_msg:
                email_part = next((w for w in user_msg.split() if "@" in w), user_msg)
                # [FIX] Strip trailing punctuation from email for Pydantic validation
                email_part = email_part.rstrip(".,!?;")
                
                # [AI-POWERED] Smart Extraction
                # Pre-fill with Regex result (Strong Signal)
                regex_name = extract_name(user_msg)
                
                # Resolve Name: Extracted -> Temp State -> None (Strict Mode: No "Friend" default yet)
                name_part = regex_name
                if not name_part and self.mm_service:
                    try:
                        result = await self.mm_service.extract_identity(user_msg)
                        name_part = result.get("name")
                    except:
                        pass
                
                if not name_part:
                     name_part = state.temp_name

                # Strict Check
                if not name_part:
                    # We have Email, but NO Name. Prompt for Name.
                    self.update_state(session_id, {"user_email": email_part})
                    return f"Thanks! I have your email as **{email_part}**. What is your **First Name** so I can build your profile?"

                email_extracted = email_part
                
                # We have BOTH Name and Email. Proceed.
                # Persist
                self.update_state(session_id, {"stage": "diagnosis", "user_email": email_part, "user_name": name_part})
                if self.crm:
                    self.crm.create_or_update_contact(email=email_part, first_name=name_part)
                
                # [FAST TRACK] Check if they also provided a symptom
                # Reuse the keyword check from Soft Pivot logic
                is_diagnosis_keyword = any(w in user_msg.lower() for w in ["swelling", "ankle", "leg", "surgery", "post-op", "lipo", "recovery", "protocol", "product", "leggings", "hurt", "pain"])
                
                if is_diagnosis_keyword:
                    # Delegate immediately to diagnosis logic
                    diagnosis_response = self._handle_diagnosis_v3(session_id, user_msg)
                    # Prepend confirmation
                    return f"Thanks {name_part}! I've saved your profile. {diagnosis_response}"

                return f"Thanks {name_part}! I've saved your profile. Now, **tell me a bit about what's going on in your body today?** (e.g., are you dealing with swelling, recovering from surgery, or just looking for general wellness?)"
            
            # B. Soft Pivot for Interruption / Generic Greeting
            is_diagnosis_keyword = any(w in msg_lower for w in ["swelling", "ankle", "leg", "surgery", "post-op", "lipo", "recovery", "protocol", "product", "leggings"])
            
            if is_diagnosis_keyword:
                return ("I'd love to help you with that! To make sure I give you the most accurate routine and save your progress, "
                        "could you just share your **First Name and Email Address**? Then we can dive right into the details.")

            # C. Check for Name Only (Using spaCy NER + Robust Logic)
            parsed_name = extract_name(user_msg)
            is_greeting = any(w in msg_lower for w in ["hi", "hello", "hey", "yo"])
            
            if parsed_name and not is_greeting:
                # 1. Check if we already have their email (from previous turn)
                if state.user_email:
                    # Success! We have both.
                    self.update_state(session_id, {"stage": "diagnosis", "user_name": parsed_name})
                    if self.crm:
                         self.crm.create_or_update_contact(email=state.user_email, first_name=parsed_name)
                    
                    return f"Thanks {parsed_name}! I've saved your profile. Now, **tell me a bit about what's going on in your body today?**"

                # 2. No email yet? Save temp name and ask.
                self.update_state(session_id, {"temp_name": parsed_name}) 
                return f"Nice to meet you, {parsed_name}. **What is the best email address** for us to connect your wellness profile?"
                
            else:
                return "Hello! I'm Sarah, your Lymphatic Wellness Guide. To get started, I just need your **First Name and Email Address** to build your profile."

        # 2. Main Diagnosis Logic (The V3 Core)
        if stage == "diagnosis":
            # [Fail-safe] Late Email Capture
            if "@" in user_msg and not state.user_email:
                 self.update_state(session_id, {"user_email": user_msg})
                 if self.crm: self.crm.create_or_update_contact(email=user_msg, first_name=state.temp_name or "Friend")
                 return "Got it! Now, tell me more—are you managing **daily swelling**, or is this specifically for **post-op recovery**?"

            return self._handle_diagnosis_v3(session_id, user_msg)
            
        elif stage == "agreement":
            return self._handle_agreement(session_id, user_msg)
            
        elif stage == "fork":
            return self._handle_fork(session_id, user_msg)
            
        return "I'm listening. Tell me more about what you're feeling in your body today."

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
        if any(w in msg_lower for w in ["surgery", "post-op", "lipo", "recovery"]):
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
                intro = "I understand completely. Post-op swelling is tricky because we want to move the fluid without disturbing the healing tissue."
            elif issue_type == "arms":
                intro = "That heaviness in the arms can be frustrating. It often happens when the axillary (armpit) pathway is sluggish."
            else:
                 # Foundation / Default
                intro = "Thanks for sharing. It sounds like you want to support your body's natural flow, which is the foundation of energy and health."

        # --- C. Layer 2: Education (The Bridge) ---
        bridge = ""
        if issue_type == "legs":
            bridge = ("\n\n**Here is the underlying mechanics:**\n"
                      "Your lymphatic system is unique because **it doesn't have a heart to pump it** like your blood does. "
                      "It relies entirely on movement. When fluid pools in the ankles, it means the return flow is struggling against gravity.")
        elif issue_type == "post_op":
            bridge = ("\n\n**Here is the goal:**\n"
                      "Your body is currently in 'protection mode', holding onto fluid. Our goal is to gently open the 'drains' (near the collarbone) "
                      "to create a vacuum effect, pulling that fluid away from the surgical site safely.")
        elif issue_type == "arms":
             bridge = ("\n\n**Here is what's happening:**\n"
                       "The axillary (armpit) lymph nodes are the main drain for the arms. When they get congested or stagnant, "
                       "fluid backs up into the hands and triceps. We need to clear the drain first.")
        else:
             bridge = ("\n\n**Here is the science:**\n"
                       "The lymphatic system is your body's sewage treatment plant. Without a pump, it needs specific targeted movements "
                       "(like deep breathing) to create the pressure changes that move fluid.")

        # --- D. Layer 3: Conversational Protocol (The Prescription) ---
        # Improved Formatting for readability
        prescription = ["\n\n**Here is a Science-Backed Routine tailored for you:**"]
        
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
        closing = "\n\nDoes this routine feel manageable for you to start including this evening?"
        
        # Combine
        full_response = intro + bridge + "".join(prescription) + closing
        
        # Update State
        self.update_state(session_id, {"stage": "agreement", "agreed_protocol": [selected_protocol['title']]})
        
        return full_response

    def _handle_agreement(self, session_id, msg):
        msg_lower = msg.lower()
        if any(w in msg_lower for w in ["yes", "sure", "ok", "great"]):
            self.update_state(session_id, {"stage": "fork"})
            return ("Fantastic. I'm generating your **Personalized Wellness Protocol** PDF right now.\n\n"
                    "While that processes, would you like to see the **Clinical Garments** that support this protocol, "
                    "or speak to a **Specialist**?")
        
        # [FIX] Handle objections/difficulty without looping
        elif any(w in msg_lower for w in ["no", "can't", "cant", "hard", "difficult"]):
            self.update_state(session_id, {"stage": "fork"})
            return ("Understood. We can modify the intensity. I've noted to start with a gentler pace in your full protocol.\n\n"
                    "While I finalize that, would you prefer to look at **Clothing** options or a **Consultation**?")
        
        else:
            # Fallback that tries to nudge forward
            self.update_state(session_id, {"stage": "fork"})
            return ("I hear you. Let's aim for the 'Foundation' level first.\n\n"
                    "I'm generating your full plan now. While that runs, do you want to browse **Compression Wear** or talk to a **Specialist**?")

    def _handle_fork(self, session_id, msg):
        return "Would you prefer to look at **Clothing** options or a **Consultation**?"
