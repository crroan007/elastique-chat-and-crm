"""
Elastique CRM Schema Migration v3
=================================
Adds: Workflows, Pipelines, Tags, Email Tracking

Patterns inspired by:
- Twenty: Workflow action/execution model
- Krayin: Pipeline stages with probability
- Monica: Author attribution, soft deletes

Run: python migrate_v3_crm.py
"""

import sqlite3
import uuid
from datetime import datetime

DB_PATH = "data/elastique.db"

def get_uuid():
    return str(uuid.uuid4())

def now():
    return datetime.now().isoformat()

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 50)
    print("ELASTIQUE CRM SCHEMA MIGRATION V3")
    print("=" * 50)
    
    # =============================================
    # 1. PIPELINES (Krayin pattern)
    # =============================================
    print("\n[1/6] Creating pipelines tables...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_stages (
            id TEXT PRIMARY KEY,
            pipeline_id TEXT REFERENCES pipelines(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            color TEXT DEFAULT '#636E72',
            sort_order INTEGER DEFAULT 0,
            probability INTEGER DEFAULT 50,
            stale_after_days INTEGER DEFAULT 14,
            created_at TEXT
        )
    """)
    
    # Seed default pipeline
    cursor.execute("SELECT COUNT(*) FROM pipelines")
    if cursor.fetchone()[0] == 0:
        pipeline_id = get_uuid()
        cursor.execute("""
            INSERT INTO pipelines (id, name, description, is_default, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (pipeline_id, "Default Pipeline", "Standard sales pipeline", 1, now()))
        
        # Seed default stages
        stages = [
            ("New Lead", "#3498db", 0, 10),
            ("Contacted", "#9b59b6", 1, 25),
            ("Qualified", "#f39c12", 2, 50),
            ("Proposal", "#e67e22", 3, 75),
            ("Won", "#00B894", 4, 100),
            ("Lost", "#e74c3c", 5, 0),
        ]
        for name, color, order, prob in stages:
            cursor.execute("""
                INSERT INTO pipeline_stages (id, pipeline_id, name, color, sort_order, probability, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (get_uuid(), pipeline_id, name, color, order, prob, now()))
        print("  + Created default pipeline with 6 stages")
    else:
        print("  - Pipelines already exist, skipping seed")
    
    # =============================================
    # 2. WORKFLOWS (Twenty pattern)
    # =============================================
    print("\n[2/6] Creating workflows tables...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            trigger_type TEXT NOT NULL DEFAULT 'event',
            trigger_event TEXT,
            trigger_schedule TEXT,
            is_active INTEGER DEFAULT 1,
            is_published INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_steps (
            id TEXT PRIMARY KEY,
            workflow_id TEXT REFERENCES workflows(id) ON DELETE CASCADE,
            step_order INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            action_config TEXT,
            condition_logic TEXT,
            created_at TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT REFERENCES workflows(id),
            contact_id TEXT REFERENCES contacts(id),
            trigger_event TEXT,
            trigger_data TEXT,
            started_at TEXT,
            completed_at TEXT,
            status TEXT DEFAULT 'running',
            current_step INTEGER DEFAULT 0,
            context TEXT,
            error_message TEXT
        )
    """)
    
    print("  + workflows, workflow_steps, workflow_executions created")
    
    # =============================================
    # 3. CONTACT TAGS (Krayin pattern)
    # =============================================
    print("\n[3/6] Creating contact_tags table...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_tags (
            id TEXT PRIMARY KEY,
            contact_id TEXT REFERENCES contacts(id) ON DELETE CASCADE,
            tag TEXT NOT NULL,
            created_by TEXT DEFAULT 'system',
            created_at TEXT
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_contact ON contact_tags(contact_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON contact_tags(tag)")
    
    print("  + contact_tags with indexes created")
    
    # =============================================
    # 4. EMAIL TEMPLATES & TRACKING
    # =============================================
    print("\n[4/6] Creating email tracking tables...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            subject TEXT,
            body_html TEXT,
            body_text TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_sends (
            id TEXT PRIMARY KEY,
            campaign_id TEXT REFERENCES campaigns(id),
            contact_id TEXT REFERENCES contacts(id),
            template_id TEXT REFERENCES email_templates(id),
            sent_at TEXT,
            status TEXT DEFAULT 'queued',
            external_id TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_events (
            id TEXT PRIMARY KEY,
            email_send_id TEXT REFERENCES email_sends(id),
            event_type TEXT NOT NULL,
            metadata TEXT,
            occurred_at TEXT
        )
    """)
    
    print("  + email_templates, email_sends, email_events created")
    
    # =============================================
    # 5. ENHANCED DEALS (Krayin pattern)
    # =============================================
    print("\n[5/6] Enhancing deals table...")
    
    try:
        cursor.execute("ALTER TABLE deals ADD COLUMN pipeline_id TEXT")
        print("  + Added pipeline_id to deals")
    except sqlite3.OperationalError:
        print("  - pipeline_id already exists")
    
    try:
        cursor.execute("ALTER TABLE deals ADD COLUMN pipeline_stage_id TEXT")
        print("  + Added pipeline_stage_id to deals")
    except sqlite3.OperationalError:
        print("  - pipeline_stage_id already exists")
    
    try:
        cursor.execute("ALTER TABLE deals ADD COLUMN expected_close_at TEXT")
        print("  + Added expected_close_at to deals")
    except sqlite3.OperationalError:
        print("  - expected_close_at already exists")
    
    try:
        cursor.execute("ALTER TABLE deals ADD COLUMN lost_reason TEXT")
        print("  + Added lost_reason to deals")
    except sqlite3.OperationalError:
        print("  - lost_reason already exists")
    
    # =============================================
    # 6. AUTHOR ATTRIBUTION (Monica pattern)
    # =============================================
    print("\n[6/6] Adding author attribution...")
    
    try:
        cursor.execute("ALTER TABLE timeline_events ADD COLUMN created_by TEXT")
        print("  + Added created_by to timeline_events")
    except sqlite3.OperationalError:
        print("  - created_by already exists")
    
    try:
        cursor.execute("ALTER TABLE contact_notes ADD COLUMN sentiment TEXT")
        print("  + Added sentiment to contact_notes")
    except sqlite3.OperationalError:
        print("  - sentiment already exists")
    
    # Commit all changes
    conn.commit()
    
    # =============================================
    # VERIFICATION
    # =============================================
    print("\n" + "=" * 50)
    print("VERIFICATION")
    print("=" * 50)
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [t[0] for t in cursor.fetchall()]
    
    required = [
        'pipelines', 'pipeline_stages',
        'workflows', 'workflow_steps', 'workflow_executions',
        'contact_tags',
        'email_templates', 'email_sends', 'email_events'
    ]
    
    all_present = True
    for table in required:
        if table in tables:
            print(f"  ✓ {table}")
        else:
            print(f"  ✗ {table} MISSING!")
            all_present = False
    
    conn.close()
    
    if all_present:
        print("\n✅ Migration v3 completed successfully!")
    else:
        print("\n❌ Some tables are missing. Check errors above.")
    
    return all_present

if __name__ == "__main__":
    migrate()
