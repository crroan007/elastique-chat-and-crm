import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime

# Setup Logging
# logging.basicConfig(level=logging.INFO) # REMOVED: Managed by server.py
logger = logging.getLogger(__name__)

class ConsultantBrain:
    def __init__(self, products_file="elastique_products.json", science_file="scientific_library.json", persona_file="consultant_persona.txt"):
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
             logger.error("CRITICAL: GEMINI_API_KEY NOT FOUND")
        else:
             genai.configure(api_key=self.api_key)

        self.products_db = self._load_json(products_file)
        self.science_db = self._load_json(science_file)
        self.system_prompt = self._load_text(persona_file)
        self.model_name = "gemini-2.5-pro"
        self.user_sessions = {}

    def _load_json(self, filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            return []

    def _load_text(self, filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            return "You are a helpful assistant."

    def _log_conversation(self, role, message):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Sanitize newlines
            clean_msg = message.replace("\n", " ")
            with open("server_conversation.txt", "a", encoding="utf-8") as f:
                f.write(f"{timestamp} | {role} | {clean_msg}\n")
        except Exception as e:
            logger.error(f"Failed to log conversation: {e}")

    def find_relevant_products(self, query: str):
        """Keyword search returning Top 2 matches (Strict Filter)"""
        query = query.lower()
        matches = []
        
        # 1. INTENT CHECK (Optional but recommended)
        # If user is just saying "Hello" or "I hurt my leg", we shouldn't show products immediately.
        # But for now, let's just fix the "Bad Match" issue first.
        
        # 2. DEFINED MAPPINGS (Body Part -> Category)
        # If user mentions body part, prioritize that category.
        target_category = None
        if any(w in query for w in ["ankle", "leg", "calf", "knee", "thigh", "foot"]):
            target_category = "legging" # or bottom, short
        elif any(w in query for w in ["arm", "shoulder", "chest", "back", "breast"]):
            target_category = "bra" # or top, tank
        elif any(w in query for w in ["stomach", "waist", "abdomen", "belly"]):
            target_category = "legging" 

        # 3. STOP WORDS (The Root Cause of "Bra matches 'in'")
        stop_words = {"in", "on", "at", "the", "a", "an", "my", "i", "is", "for", "to", "of", "and", "with", "it"}
        query_terms = [w for w in query.split() if w not in stop_words and len(w) > 2]
        
        if not query_terms:
            return []

        # 4. SEARCH EXECUTION
        scores = [] # (product, score)
        
        for p in self.products_db:
            score = 0
            title = p.get("title", "").lower()
            desc = p.get("description", "").lower()
            
            # Category Boost
            if target_category:
                if target_category == "legging" and ("legging" in title or "short" in title or "bottom" in p.get("style", "").lower()):
                    score += 5
                elif target_category == "bra" and ("bra" in title or "tank" in title or "top" in title):
                     score += 5
                # Anti-Boost (Don't show Bras for Leg problems)
                elif target_category == "legging" and ("bra" in title or "top" in title):
                    score -= 10
            
            # Keyword Matching
            for term in query_terms:
                if term in title:
                    score += 3
                elif term in desc:
                    score += 1
            
            if score > 0:
                scores.append((p, score))
        
        # Sort by Score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return Top 2 (only if positive score)
        return [item[0] for item in scores[:2] if item[1] > 0]

    def find_relevant_research(self, query: str):
        """Search scientific library for relevant facts/URLs"""
        query = query.lower()
        hits = []
        
        for entry in self.science_db:
            if entry.get("category", "").lower() in query:
                 hits.append(entry)
                 continue
            for fact in entry.get("facts", []):
                if any(w in query for w in entry.get("mechanism", "").lower().split()) or \
                   any(w in query for w in fact.get("statement", "").lower().split()):
                    hits.append(entry)
                    break
        
        if not hits:
            return "General Lymphatic Principles apply. Focus on: Graduated Compression and Micro-Massage."
            
        context_str = "RELEVANT RESEARCH (CITE THESE SPECIFICALLY):\n"
        for h in hits[:2]:
            context_str += f"- Category: {h['category']}\n"
            context_str += f"- Mechanism: {h['mechanism']}\n"
            for f in h["facts"]:
                url = f.get("url", "https://pubmed.ncbi.nlm.nih.gov/")
                context_str += f"  * {f['statement']} (Source: {url})\n"
        return context_str

    def get_session(self, session_id, user_name=None, user_email=None):
        if session_id not in self.user_sessions:
            user_context = ""
            if user_name:
                user_context = f"\nUSER CONTEXT:\nName: {user_name}\nEmail: {user_email}\n"
            
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_prompt + user_context
            )
            self.user_sessions[session_id] = model.start_chat(history=[])
            logger.info(f"Created new session for {session_id}")
        return self.user_sessions[session_id]

    async def chat_stream(self, message: str, file_bytes=None, file_mime=None, user_name=None, user_email=None):
        """
        Yields:
          - {"type": "product_card", "content": ...}
          - {"type": "text", "content": ...}
        """
        self._log_conversation("USER", message)
        session_id = user_email if user_email else "guest"
        chat = self.get_session(session_id, user_name, user_email)

        # DEBUG: Log History
        logger.debug(f"--- CHAT HISTORY BEFORE TURN for {session_id} ---")
        try:
            for content in chat.history:
                logger.debug(f"{content.role}: {content.parts[0].text[:50]}...")
        except Exception as e:
            logger.debug(f"Could not log history: {e}")
        
        # RAG Logic
        import time
        t_start = time.time()
        suggested_products = self.find_relevant_products(message)
        t_prod = time.time()
        research_context = self.find_relevant_research(message)
        t_end = time.time()
        logger.debug(f"[PERFORMANCE] RAG Lookup: Products={t_prod-t_start:.4f}s, Research={t_end-t_prod:.4f}s")

        # System Injection
        system_injection = "\n\n[SYSTEM INJECTION]:\n"
        if suggested_products:
            prod_data = json.dumps([{ "title": p["title"], "url": p["product_url"] } for p in suggested_products])
            system_injection += f"1. POTENTIALLY RELEVANT INVENTORY (Mention ONLY if directly relevant to the user's specific problem): {prod_data}\n"
        system_injection += f"2. {research_context}"
        
        # DEBUG: Log System Injection
        logger.debug(f"SYSTEM INJECTION: {system_injection}")

        # 1. Yield Product Cards First
        if suggested_products:
            cards = ""
            for p in suggested_products:
                title = p.get("title", "Product")
                img = p.get("image_url", "")
                url = p.get("product_url", "#")
                price = p.get("price", "")
                
                cards += f"""
                <div class="ghl-product-tile" style="min-width: 200px; border: 1px solid #eee; border-radius: 8px; padding: 10px; background: white; margin-right: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                    <img src="{img}" alt="{title}" style="width: 100%; height: 150px; object-fit: cover; border-radius: 4px; margin-bottom: 8px;">
                    <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px; color: #333;">{title}</div>
                    <div style="font-size: 13px; color: #666; margin-bottom: 8px;">{price}</div>
                    <a href="{url}" target="_blank" style="display: block; text-align: center; background: #6C5CE7; color: white; padding: 8px; border-radius: 4px; text-decoration: none; font-size: 13px; font-weight: 600;">View Product</a>
                </div>
                """
            if cards:
                card_html = f'<div style="display: flex; gap: 10px; overflow-x: auto; padding-bottom: 10px;">{cards}</div>'
                yield {"type": "product_card", "content": card_html}

        # 2. Call Gemini
        try:
            if file_bytes:
                content_parts = [{"mime_type": file_mime or "image/jpeg", "data": file_bytes}, message + system_injection]
                response = chat.send_message(content_parts, stream=True)
            else:
                response = chat.send_message(message + system_injection, stream=True)
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            yield {"type": "text", "content": "I'm having trouble connecting to my brain right now. Please try again."}
            return
        full_response = ""
        try:
            for chunk in response:
                text = chunk.text
                if text:
                    full_response += text
                    yield {"type": "text", "content": text}
        except Exception as e:
            logger.error(f"Stream Error: {e}")
        
        self._log_conversation("BOT", full_response)
