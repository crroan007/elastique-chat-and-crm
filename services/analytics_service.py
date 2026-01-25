import logging
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class AnalyticsService:
    """
    Handles telemetry logging for the Elastique Chatbot.
    Writes to database (PostgreSQL) in production, or Console/Log in dev.
    """
    
    def __init__(self, db_connection_string: Optional[str] = None):
        self.db_url = db_connection_string
        self.is_connected = False
        if self.db_url:
            self._connect()
        else:
            logger.info("Analytics: Running in HEADLESS mode (Console Logging Only)")

    def _connect(self):
        # Stub for DB connection (psycopg2 or sqlalchemy)
        # self.conn = psycopg2.connect(self.db_url)
        self.is_connected = True
        logger.info("Analytics: Connected to Database")

    def track_session_start(self, session_id: str, metadata: Dict):
        """
        Logs a new session arrival.
        """
        event = {
            "event": "session_start",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata
        }
        self._log("conversations", event)

    def track_message(self, session_id: str, sender: str, content: str, tokens: int = 0):
        """
        Logs a message exchange (User or Bot).
        """
        event = {
            "event": "message",
            "session_id": session_id,
            "sender": sender,
            "content_snippet": content[:50] + "..." if len(content) > 50 else content,
            "tokens": tokens
        }
        self._log("messages", event)

    def track_lead_capture(self, session_id: str, email: str, source: str = "chat"):
        """
        Logs a successful email capture.
        """
        event = {
            "event": "lead_captured",
            "session_id": session_id,
            "email": email,
            "source": source
        }
        self._log("contacts", event)

    def track_protocol_generated(self, session_id: str, protocol_items: List[str]):
        """
        Logs the generation of a PDF protocol.
        """
        event = {
            "event": "protocol_generated",
            "session_id": session_id,
            "items_count": len(protocol_items),
            "items": protocol_items
        }
        self._log("conversations", event)

    def track_product_interaction(self, session_id: str, product_name: str, action: str):
        """
        Logs product views, clicks, or recommendations.
        action: 'recommendation', 'view', 'click'
        """
        event = {
            "event": "product_interaction",
            "session_id": session_id,
            "product": product_name,
            "action": action
        }
        self._log("product_events", event)

    def track_issue_mention(self, session_id: str, category: str, keyword: str):
        """
        Logs taxonomy tags (e.g., Body Part: Ankle, Symptom: Swelling).
        """
        event = {
            "event": "issue_mention",
            "session_id": session_id,
            "category": category,
            "keyword": keyword
        }
        self._log("issue_mentions", event)

    def _log(self, table: str, data: Dict):
        """
        Internal dispatcher.
        """
        # Console Output
        print(f"\n[TELEMETRY] [{table.upper()}] {json.dumps(data, default=str)}")
        
        # File Persistence (Simple JSON Log for V0 CRM)
        try:
            log_entry = {
                "table": table,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            with open("data/events.log.json", "a") as f:
                f.write(json.dumps(log_entry, default=str) + "\n")
        except Exception as e:
            print(f"Analytics Write Error: {e}")

        if self.is_connected:
            # self.cursor.execute(f"INSERT INTO {table} ...")
            pass
