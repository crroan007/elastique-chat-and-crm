import logging
import json
import uuid
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

# [AGENT] The Analyst Agent
# Uses Gemini to extract structured business metrics from unstructured chat logs.

logger = logging.getLogger(__name__)

DB_PATH = "data/elastique.db"

class ConversationAnalyst:
    def __init__(self, multimodal_service=None, db_path=DB_PATH):
        self.mm = multimodal_service
        self.db_path = db_path

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def analyze_session(self, session_id: str, context: Optional[str] = None):
        """
        Main entry point.
        1. Fetch Transcript.
        2. Prompt Gemini.
        3. Save Metrics.
        """
        transcript = self._fetch_transcript(session_id)
        if not transcript:
            logger.warning(f"Analyst: No transcript found for {session_id}")
            return None

        # [AGENT] The Prompt
        prompt = f"""
        Act as a Medical Office Manager. Analyze this chat transcript between a user and 'Sarah' (Bot).
        
        Transcript:
        {transcript}
        
        Extract the following Business Metrics in strict JSON format:
        1. "user_need": A 1-sentence summary of the user's specific problem (e.g., "Post-op swelling after lipo").
        2. "plan_provided": A 1-sentence summary of what Sarah recommended (e.g., "Leg draining protocol").
        3. "alignment_met": Boolean. Did the user explicitly agree/commit to the plan? Match phrases like "Yes", "I'll try", "Sounds good".
        4. "products_discussed": List of strings (e.g., ["Compression Socks", "Leggings"]).
        5. "appointment_scheduled": Boolean. Was a consultation booked?
        6. "appointment_date": ISO8601 String or null.
        
        Output JSON Only. No markdown.
        """

        metrics = {}
        
        # [MOCK vs REAL]
        if self.mm and self.mm.model:
            try:
                response = self.mm.model.generate_content(prompt)
                cleaned = response.text.replace("```json", "").replace("```", "").strip()
                metrics = json.loads(cleaned)
            except Exception as e:
                logger.error(f"Analyst Agent Failed: {e}")
                # Fallback / Retry logic could go here
                return None
        else:
            logger.info("Analyst: Running in SMART MOCK mode (No Gemini Key).")
            # Simple keyword extraction for testing/fallback
            lower_trans = transcript.lower()
            
            # 1. Need
            mock_need = "General Wellness"
            if "swelling" in lower_trans: mock_need = "Swelling/Lymphedema management"
            elif "surgery" in lower_trans or "post-op" in lower_trans: mock_need = "Post-Op Recovery"
            
            # 2. Plan
            mock_plan = "Foundation Protocol"
            if "drainage" in lower_trans: mock_plan = "Lymphatic Drainage Protocol"
            
            # 3. Alignment (Look for agreement after protocol)
            mock_align = "yes" in lower_trans or "sounds good" in lower_trans or "i will" in lower_trans
            
            # 4. Products
            mock_products = []
            if "socks" in lower_trans: mock_products.append("Compression Socks")
            if "leggings" in lower_trans: mock_products.append("Compression Leggings")
            
            # 5. Appointment
            mock_appt = "book" in lower_trans or "schedule" in lower_trans or "friday" in lower_trans
            
            metrics = {
                "user_need": mock_need,
                "plan_provided": mock_plan,
                "alignment_met": mock_align,
                "products_discussed": mock_products,
                "appointment_scheduled": mock_appt,
                "appointment_date": datetime.now().isoformat() if mock_appt else None
            }

        # Save to DB
        self._save_metrics(session_id, metrics)
        return metrics

    def _fetch_transcript(self, session_id: str) -> str:
        """
        Reconstructs the conversation from the DB messages table.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get Conversation ID
        print(f"Analyst: Fetching transcript for session {session_id}")
        cursor.execute("SELECT id FROM conversations WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            print(f"Analyst: Session {session_id} not found in conversations table.")
            conn.close()
            return ""
            
        conversation_id = row['id']
        print(f"Analyst: Found conversation_id {conversation_id}")
        
        # Get Messages
        cursor.execute("SELECT sender, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,))
        rows = cursor.fetchall()
        print(f"Analyst: Found {len(rows)} messages.")
        
        transcript = ""
        for r in rows:
            transcript += f"{r['sender'].upper()}: {r['content']}\n"
            
        conn.close()
        return transcript

    def _save_metrics(self, session_id: str, metrics: Dict):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get Conversation ID
        cursor.execute("SELECT id FROM conversations WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        
        conversation_id = row['id']
        metric_id = str(uuid.uuid4())
        
        # Upsert Logic (Delete old metrics for this convo first to keep 1:1)
        cursor.execute("DELETE FROM conversation_metrics WHERE conversation_id = ?", (conversation_id,))
        
        cursor.execute("""
            INSERT INTO conversation_metrics (
                id, conversation_id, user_need, plan_provided, alignment_met, 
                products_discussed, appointment_scheduled, appointment_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metric_id, conversation_id,
            metrics.get("user_need"),
            metrics.get("plan_provided"),
            metrics.get("alignment_met", False),
            json.dumps(metrics.get("products_discussed", [])),
            metrics.get("appointment_scheduled", False),
            metrics.get("appointment_date")
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Analyst: Saved metrics for session {session_id}")
