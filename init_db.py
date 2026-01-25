import sqlite3
import os
import uuid
import json
from datetime import datetime, timedelta

DB_PATH = "data/elastique.db"
SCHEMA_PATH = "database/schema_sqlite.sql"

def init_db():
    # Ensure data dir exists
    if not os.path.exists("data"):
        os.makedirs("data")

    # Remove old DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed old database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Read Schema
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()
    
    # Execute Schema
    cursor.executescript(schema)
    print("Schema applied successfully.")

    # Seed Data (The 6 Personas)
    seed_contacts(cursor)

    conn.commit()
    conn.close()
    print("Database initialization complete.")

def seed_contacts(cursor):
    personas = [
        {
            "email": "sarah@mom.test", "first_name": "Sarah", "last_name": "Miller", 
            "lifecycle": "lead", "source": "Facebook Ad (Postpartum)",
            "concerns": ["swelling", " ankles"], "score": 85.0, "ltv": 0.0,
            "notes": "Busy mom of 3. Needs quick routine. High swelling in evenings.",
            "ticket": None
        },
        {
            "email": "skeptic@test.com", "first_name": "David", "last_name": "Chen", 
            "lifecycle": "customer", "source": "Organizer Search",
            "concerns": ["efficacy", "science"], "score": 45.0, "ltv": 120.0,
            "notes": "Asked for citation papers. Very analytical. Bought socks previously.",
            "ticket": "Subject: Return Policy Inquiry - [Open]"
        },
        {
            "email": "jenny@postop.test", "first_name": "Jenny", "last_name": "L.", 
            "lifecycle": "lead", "source": "Surgeon Referral",
            "concerns": ["post-op", "tummy tuck"], "score": 95.0, "ltv": 0.0,
            "notes": "2 weeks post-op. Caution advised. Cleared for gentle walking.",
            "ticket": "Subject: Sizing for Post-Op - [High Priority]"
        },
        {
            "email": "mike@tennis.test", "first_name": "Mike", "last_name": "Ross", 
            "lifecycle": "vip", "source": "Direct",
            "concerns": ["arm", "performance"], "score": 92.0, "ltv": 450.0,
            "notes": "Competitive tennis player. Heavy user of compression sleeves.",
            "ticket": None
        },
        {
            "email": "rush@buy.test", "first_name": "Alex", "last_name": "Rusher", 
            "lifecycle": "visitor", "source": "Instagram Story",
            "concerns": ["price", "shipping"], "score": 30.0, "ltv": 0.0,
            "notes": "Skipped diagnosis. Just wanted link.",
            "ticket": None
        },
    ]

    for p in personas:
        cid = str(uuid.uuid4())
        
        # Insert Contact
        cursor.execute("""
            INSERT INTO contacts (id, email, first_name, last_name, lifecycle_stage, acquisition_source, primary_concerns, engagement_score, lifetime_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cid, p["email"], p["first_name"], p["last_name"], p["lifecycle"], p["source"], 
            json.dumps(p["concerns"]), p["score"], p["ltv"], 
            (datetime.now() - timedelta(days=random_days())).isoformat()
        ))

        # Insert Identity
        cursor.execute("INSERT INTO contact_identities (id, contact_id, identity_type, identity_value) VALUES (?, ?, 'email', ?)", 
                       (str(uuid.uuid4()), cid, p["email"]))

        # Insert Manual Note
        cursor.execute("INSERT INTO contact_notes (id, contact_id, content, author_id) VALUES (?, ?, ?, 'system')",
                       (str(uuid.uuid4()), cid, p["notes"]))

        # Insert Ticket if exists
        if p["ticket"]:
             subject = p["ticket"].split(":")[1].strip()
             tid = str(uuid.uuid4())
             cursor.execute("INSERT INTO support_tickets (id, contact_id, subject, description) VALUES (?, ?, ?, ?)",
                            (tid, cid, subject, "Automated ticket from chat context."))

        # Insert Mock Deal + History (For Historical Reporting Demo)
        if p["lifecycle"] in ["customer", "lead", "vip"]:
            did = str(uuid.uuid4())
            amount = p.get("ltv", 0) + 150.0 # Potential value
            stage = "closed_won" if p["lifecycle"] in ["customer", "vip"] else "protocol_sent"
            
            # Create Deal
            cursor.execute("INSERT INTO deals (id, contact_id, stage, amount) VALUES (?, ?, ?, ?)",
                           (did, cid, stage, amount))
            
            # Create Deal History (Backdated)
            # 1. Created (30 days ago)
            cursor.execute("INSERT INTO deal_history (id, deal_id, previous_stage, new_stage, changed_at) VALUES (?, ?, ?, ?, ?)",
                           (str(uuid.uuid4()), did, None, "new", (datetime.now() - timedelta(days=30)).isoformat()))
            
            # 2. Protocol Sent (15 days ago)
            cursor.execute("INSERT INTO deal_history (id, deal_id, previous_stage, new_stage, changed_at) VALUES (?, ?, ?, ?, ?)",
                           (str(uuid.uuid4()), did, "new", "protocol_sent", (datetime.now() - timedelta(days=15)).isoformat()))
            
            # 3. Won (5 days ago - if applicable)
            if stage == "closed_won":
                cursor.execute("INSERT INTO deal_history (id, deal_id, previous_stage, new_stage, changed_at) VALUES (?, ?, ?, ?, ?)",
                               (str(uuid.uuid4()), did, "protocol_sent", "closed_won", (datetime.now() - timedelta(days=5)).isoformat()))

def random_days():
    import random
    return random.randint(0, 60)

if __name__ == "__main__":
    init_db()
