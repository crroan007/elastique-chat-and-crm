import sqlite3
import os

DB_PATH = "data/elastique.db"

def migrate():
    print("--- Migrating Database to V3 (Conversation Metrics) ---")
    if not os.path.exists(DB_PATH):
        print("Database not found. Skipping migration (will be created by init_db).")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("Creating Table: conversation_metrics...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_metrics (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                
                user_need TEXT,
                plan_provided TEXT,
                alignment_met BOOLEAN DEFAULT 0,
                
                products_discussed TEXT, -- JSON List
                
                appointment_scheduled BOOLEAN DEFAULT 0,
                appointment_date TEXT,
                
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
        """)
        
        # Verify
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_metrics'")
        if cursor.fetchone():
            print("SUCCESS: Table 'conversation_metrics' verified.")
        else:
            print("FAIL: Table was not created.")

        conn.commit()
    except Exception as e:
        print(f"Migration Failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
