
import sqlite3

def migrate_v2_1():
    print("--- MIGRATING TO ELASTIQUE CRM V2.1 (Transcripts) ---")
    conn = sqlite3.connect('data/elastique.db')
    cursor = conn.cursor()
    
    # Add transcript column to timeline_events
    try:
        cursor.execute("ALTER TABLE timeline_events ADD COLUMN transcript TEXT")
        print("ADDED column: transcript")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("INFO: Column 'transcript' already exists.")
        else:
            print(f"WARN: {e}")

    # Add source_channel column (to distinguish text vs web vs phone explicitly if event_type isn't enough)
    try:
        cursor.execute("ALTER TABLE timeline_events ADD COLUMN source_channel VARCHAR(50)")
        print("ADDED column: source_channel")
    except sqlite3.OperationalError:
        print("INFO: Column 'source_channel' already exists.")

    conn.commit()
    conn.close()
    print("SUCCESS: Schema V2.1 Applied.")

if __name__ == "__main__":
    migrate_v2_1()
