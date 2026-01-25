import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

DB_PATH = "data/elastique.db"

class CRMService:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================
    # 1. READ: The "Contact 360" Dossier
    # =========================================================
    
    def get_contact_dossier(self, contact_id: str) -> Dict[str, Any]:
        """
        Aggregates EVERYTHING about a user into a single JSON object.
        This is the engine for the "Master-Detail" view.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # A. Core Profile
        cursor.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        contact = dict(cursor.fetchone())
        
        # B. Parse JSON Fields
        for field in ['segments', 'custom_tags', 'preferences', 'primary_concerns', 
                      'body_parts_discussed', 'products_interested', 'products_purchased', 
                      'known_ips', 'utm_history']:
            if contact.get(field):
                try:
                    contact[field] = json.loads(contact[field])
                except:
                    contact[field] = []

        # C. Identities (Emails, Cookies)
        cursor.execute("SELECT identity_type, identity_value, last_seen_at FROM contact_identities WHERE contact_id = ?", (contact_id,))
        contact['identities'] = [dict(row) for row in cursor.fetchall()]

        # D. Timeline: Notes
        cursor.execute("SELECT * FROM contact_notes WHERE contact_id = ? ORDER BY created_at DESC", (contact_id,))
        notes = [dict(row) for row in cursor.fetchall()]
        for n in notes: n['timeline_type'] = 'note'

        # E. Timeline: Tickets
        cursor.execute("SELECT * FROM support_tickets WHERE contact_id = ? ORDER BY created_at DESC", (contact_id,))
        tickets = [dict(row) for row in cursor.fetchall()]
        for t in tickets: t['timeline_type'] = 'ticket'

        # F. Timeline: Deals
        cursor.execute("SELECT * FROM deals WHERE contact_id = ? ORDER BY created_at DESC", (contact_id,))
        deals = [dict(row) for row in cursor.fetchall()]
        for d in deals: d['timeline_type'] = 'deal'

        # G. Timeline: Conversations (Chat Sessions)
        cursor.execute("SELECT id, started_at, message_count, primary_intent, resolution_status FROM conversations WHERE contact_id = ? ORDER BY started_at DESC", (contact_id,))
        chats = [dict(row) for row in cursor.fetchall()]
        for c in chats: c['timeline_type'] = 'chat_session'

        # H. Unified Events (Voice, Transcripts, Orders)
        # This is the "Twenty-style" unified feed
        # We use SELECT * to get the new 'transcript' and 'source_channel' columns
        cursor.execute("SELECT * FROM timeline_events WHERE contact_id = ? ORDER BY occurred_at DESC", (contact_id,))
        events = [dict(row) for row in cursor.fetchall()]
        # Determine specific type for UI icon (voice, order, etc.) based on event_type
        for e in events: 
             e['timeline_type'] = 'event' # Generic wrapper
             # Parse metadata if string
             if isinstance(e.get('metadata'), str):
                 try: e['metadata'] = json.loads(e['metadata'])
                 except: pass

        # I. Merge & Sort Timeline
        timeline = notes + tickets + deals + chats + events
        # Sort by date (newest first)
        # Note: Chat uses 'started_at', others use 'created_at', Unified Events use 'occurred_at'
        def get_sort_time(x):
            return x.get('occurred_at') or x.get('created_at') or x.get('started_at') or ""
            
        timeline.sort(key=get_sort_time, reverse=True)
        
        contact['timeline'] = timeline
        
        conn.close()
        return contact

    def get_all_contacts_summary(self, limit=50, lifecycle_filter=None) -> List[Dict]:
        """
        Fast query for the "Smart List" Grid.
        Only returns columns needed for the table view.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = "SELECT id, email, first_name, last_name, lifecycle_stage, engagement_score, lifetime_value, last_seen_at FROM contacts"
        params = []
        
        if lifecycle_filter:
            query += " WHERE lifecycle_stage = ?"
            params.append(lifecycle_filter)
            
        query += " ORDER BY last_seen_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, tuple(params))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

        return results

    def create_or_update_contact(self, email: str, first_name: str = "Unknown", last_name: str = ""):
        """
        Creates a new contact or updates existing one based on email.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT id FROM contacts WHERE email = ?", (email,))
        row = cursor.fetchone()
        
        if row:
            contact_id = row['id']
            cursor.execute("UPDATE contacts SET last_seen_at = ?, first_name = ? WHERE id = ?", 
                           (datetime.now().isoformat(), first_name, contact_id))
        else:
            contact_id = str(uuid.uuid4())
            # Basic defaults
            cursor.execute("""
                INSERT INTO contacts (id, email, first_name, last_name, created_at, last_seen_at, lifecycle_stage, engagement_score, lifetime_value)
                VALUES (?, ?, ?, ?, ?, ?, 'lead', 10, 0)
            """, (contact_id, email, first_name, last_name, datetime.now().isoformat(), datetime.now().isoformat()))
            
        conn.commit()
        conn.close()
        return contact_id

    # =========================================================
    # 2. WRITE: CRUD Actions (Notes, Deals, Tickets)
    # =========================================================

    def add_note(self, contact_id: str, content: str, author_id="manager"):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        note_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO contact_notes (id, contact_id, content, author_id) VALUES (?, ?, ?, ?)",
            (note_id, contact_id, content, author_id)
        )
        conn.commit()
        conn.close()
        return {"id": note_id, "status": "success"}

    def get_last_interaction(self, email: str) -> Optional[Dict]:
        """
        Retrieves the most recent conversation context for a returning user.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. Find Contact ID
        cursor.execute("SELECT id, first_name FROM contacts WHERE email = ?", (email,))
        contact = cursor.fetchone()
        
        if not contact:
            conn.close()
            return None
            
        contact_id = contact['id']
        first_name = contact['first_name']
        
        # 2. Find Last Conversation (ANY interaction to show memory)
        cursor.execute("""
            SELECT primary_intent, resolution_status, started_at 
            FROM conversations 
            WHERE contact_id = ? 
            ORDER BY started_at DESC 
            LIMIT 1
        """, (contact_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        # Return what we have. If no rich conversation history, intent is None.
        return {
            "user_name": first_name,
            "intent": row['primary_intent'] if row else None,
            "stage": row['resolution_status'] if row else "active", # Map to stage logic
            "last_seen": row['started_at'] if row else None
        }

    def log_conversation_start(self, session_id: str, email: str, intent: str = None):
        """
        Creates or updates a conversation record with the primary intent.
        Used for Smart Context Retention.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 1. Get Contact ID
        cursor.execute("SELECT id FROM contacts WHERE email = ?", (email,))
        contact = cursor.fetchone()
        if not contact:
            # Auto-create contact if missing (should be handled upstream, but failsafe)
            contact_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO contacts (id, email, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
                           (contact_id, email, datetime.now().isoformat(), datetime.now().isoformat()))
        else:
            contact_id = contact['id']

        # 2. Upsert Conversation
        cursor.execute("SELECT id FROM conversations WHERE id = ?", (session_id,))
        if cursor.fetchone():
            # Update existing
            if intent:
                cursor.execute("UPDATE conversations SET primary_intent = ? WHERE id = ?", (intent, session_id))
        else:
            # Create new
            cursor.execute("""
                INSERT INTO conversations (id, contact_id, started_at, message_count, primary_intent, resolution_status)
                VALUES (?, ?, ?, 1, ?, 'active')
            """, (session_id, contact_id, datetime.now().isoformat(), intent))

            # [NEW] UNIFIED TIMELINE: Log "Chat Started"
            # This ensures the timeline shows "Chat Started on Web" mixed with "Voice Call"
            cursor.execute("""
                INSERT INTO timeline_events (id, contact_id, event_type, summary, metadata, source_channel)
                VALUES (?, ?, 'chat_started', 'New Web Conversation', ?, 'web_chat')
            """, (str(uuid.uuid4()), contact_id, json.dumps({"session_id": session_id})))

        conn.commit()
        conn.close()

    def create_ticket(self, contact_id: str, subject: str, description: str, priority="medium"):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        ticket_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO support_tickets (id, contact_id, subject, description, priority) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, contact_id, subject, description, priority)
        )
        
        # Log History
        cursor.execute(
            "INSERT INTO ticket_history (id, ticket_id, previous_status, new_status) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), ticket_id, None, "open")
        )
        
        conn.commit()
        conn.close()
        return {"id": ticket_id, "status": "created"}

    def update_deal_stage(self, deal_id: str, new_stage: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Get Old Stage
        cursor.execute("SELECT stage FROM deals WHERE id = ?", (deal_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": "Deal not found"}
            
        old_stage = row['stage']
        if old_stage == new_stage:
            return {"status": "no_change"}
            
        # Update Deal
        cursor.execute("UPDATE deals SET stage = ? WHERE id = ?", (new_stage, deal_id))
        
        # Log History (Time Travel!)
        cursor.execute(
            "INSERT INTO deal_history (id, deal_id, previous_stage, new_stage) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), deal_id, old_stage, new_stage)
        )
        
        conn.commit()
        conn.close()
        return {"status": "updated", "prev": old_stage, "new": new_stage}

    def create_order(self, contact_id: str, total_amount: float, items: List[Dict], external_id: str = None):
        """
        Ingests an order (e.g. from Shopify Webhook).
        Logs to 'orders' table AND 'timeline_events'.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        order_id = str(uuid.uuid4())
        external_id = external_id or f"ORD-{uuid.uuid4().hex[:8]}"
        
        # 1. Create Order
        cursor.execute("""
            INSERT INTO orders (id, contact_id, external_order_id, total_amount, status, created_at)
            VALUES (?, ?, ?, ?, 'paid', ?)
        """, (order_id, contact_id, external_id, total_amount, datetime.now().isoformat()))
        
        # 2. Create Items
        for item in items:
            cursor.execute("""
                INSERT INTO order_items (id, order_id, sku, product_name, quantity, price)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), order_id, item['sku'], item['name'], item['quantity'], item['price']))
            
        # 3. Log to Unified Timeline
        summary = f"Placed Order #{external_id} (${total_amount})"
        meta = {"order_id": order_id, "items": len(items)}
        cursor.execute("""
            INSERT INTO timeline_events (id, contact_id, event_type, summary, metadata, source_channel)
            VALUES (?, ?, 'order_placed', ?, ?, 'shopify')
        """, (str(uuid.uuid4()), contact_id, summary, json.dumps(meta)))
            
        conn.commit()
        conn.close()
        return {"id": order_id, "status": "success"}

    # =========================================================
    # 3. MARKETING: Segmentation Engine
    # =========================================================

    def evaluate_segment(self, segment_id: str) -> List[Dict]:
        """
        Runs the JSON criteria against the contact database to find matches.
        Updates the 'last_count' for the segment.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. Get Criteria
        cursor.execute("SELECT name, criteria FROM segments WHERE id = ?", (segment_id,))
        segment = cursor.fetchone()
        if not segment:
            conn.close()
            return []
            
        try:
            criteria = json.loads(segment['criteria']) if isinstance(segment['criteria'], str) else segment['criteria']
        except:
            conn.close()
            return [] # Invalid JSON

        # 2. Get All Contacts (MVP: In-Memory Filtering)
        # In Prod, this would be a SQL Builder.
        cursor.execute("SELECT * FROM contacts")
        all_contacts = [dict(row) for row in cursor.fetchall()]
        
        matches = []
        for contact in all_contacts:
            if self._matches_criteria(contact, criteria):
                matches.append(contact)
                
        # 3. Update Count
        cursor.execute("UPDATE segments SET last_count = ?, updated_at = ? WHERE id = ?", 
                       (len(matches), datetime.now().isoformat(), segment_id))
        conn.commit()
        conn.close()
        
        return matches

    def _matches_criteria(self, contact: Dict, criteria: Dict) -> bool:
        """
        Recursive JSON Logic Evaluator.
        Supports: AND, OR, simple field matching.
        Example: {"and": [{"lifecycle_stage": "customer"}, {"engagement_score": {">": 50}}]}
        """
        # Handle Logical Operators
        if "and" in criteria:
            return all(self._matches_criteria(contact, sub) for sub in criteria["and"])
        if "or" in criteria:
            return any(self._matches_criteria(contact, sub) for sub in criteria["or"])
            
        # Handle Field Matching
        for field, condition in criteria.items():
            value = contact.get(field)
            
            # Complex Condition (Operator) e.g. "score": {">": 50}
            if isinstance(condition, dict):
                for op, threshold in condition.items():
                    if op == ">":
                        if not (isinstance(value, (int, float)) and value > threshold): return False
                    elif op == "<":
                        if not (isinstance(value, (int, float)) and value < threshold): return False
                    elif op == "contains":
                        if not (value and threshold.lower() in str(value).lower()): return False
            # Simple Equality e.g. "lifecycle_stage": "customer"
            else:
                if value != condition:
                    return False
                    
        return True
