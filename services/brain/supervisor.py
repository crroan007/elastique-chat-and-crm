import os
import json
import logging
from langchain_core.messages import HumanMessage
from services.brain.schemas import AgentState
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize Gemini Client (Legacy SDK for Compatibility)
API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL = None

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        MODEL = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        logger.error(f"Gemini Init Failed: {e}")
else:
    logger.warning("GOOGLE_API_KEY missing. Supervisor will use fallback.")

SUPERVISOR_SYSTEM_PROMPT = """
You are the Supervisor Brain of Elastique, a lymphatic health wellness guide.
Your job is to ROUTE the user's request to the correct Worker Agent.

ROUTING RULES:
- "clinical": Medical questions, symptom analysis, protocol checks, "can I take X with Y?".
- "crm": Scheduling, pricing, account status, email updates, "restart chat", "speak to human".
- "protocol": Requests for specific Elastic protocols (e.g. "Protocol 1", "swelling protocol").
- "general": Greetings, thanks, small talk, "who are you?".

OUTPUT FORMAT:
Return ONLY a JSON object:
{"intent": "clinical" | "crm" | "protocol" | "general", "confidence": float}
"""

def fallback_keyword_router(text: str) -> str:
    """Deterministic fallback if LLM fails."""
    text_lower = text.lower()
    
    # CRM Keywords
    if any(k in text_lower for k in ["restart", "reset", "email", "ticket", "human", "support", "price", "cost"]):
        return "crm"
        
    # Protocol Keywords
    if "protocol" in text_lower:
        return "protocol"
        
    # Clinical Keywords (Broad)
    if any(k in text_lower for k in ["symptom", "pain", "swelling", "lymphedema", "hurt", "advice", "medical", "take", "interactions"]):
        return "clinical"
        
    return "general"

def supervisor_worker(state: AgentState) -> dict:
    """
    Supervisor Node: Classifies intent and routes to next worker.
    Uses Gemini 1.5 Flash (google.generativeai) with Keyword Fallback.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"next_node": "END"}
        
    last_message = messages[-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    intent = "general"
    
    if MODEL:
        try:
            # Combine System Prompt + User Message
            full_prompt = f"{SUPERVISOR_SYSTEM_PROMPT}\n\nUser Output Check:\n{user_text}"
            
            # Generate
            response = MODEL.generate_content(full_prompt)
            
            # Parse
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            # Handle case where model adds "json" prefix without backticks
            if raw_text.lower().startswith("json"):
                raw_text = raw_text[4:].strip()
                
            result = json.loads(raw_text)
            intent = result.get("intent", "general")
            
        except Exception as e:
            logger.error(f"Supervisor LLM Error: {e} -> Using Fallback")
            print(f"Supervisor LLM Error: {e}") # For verify script
            intent = fallback_keyword_router(user_text)
    else:
        print("Supervisor: No Model -> Using Fallback")
        intent = fallback_keyword_router(user_text)
        
    # Mapping intent to node names
    node_mapping = {
        "clinical": "clinical_worker",
        "protocol": "protocol_worker",
        "crm": "crm_worker",
        "general": "general_worker"
    }
    
    next_node = node_mapping.get(intent, "general_worker")
    
    return {
        "next_node": next_node,
        "context": {"current_intent": intent} # Update context
    }
