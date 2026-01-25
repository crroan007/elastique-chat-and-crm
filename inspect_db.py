import sqlite3
import pandas as pd

def inspect_db():
    conn = sqlite3.connect("data/elastique.db")
    
    print("\n--- CONTACTS (Last 5) ---")
    try:
        df_contacts = pd.read_sql_query("SELECT id, email, first_name, last_seen_at FROM contacts ORDER BY created_at DESC LIMIT 5", conn)
        print(df_contacts)
    except Exception as e:
        print(e)
        
    print("\n--- CONVERSATIONS (Last 5) ---")
    try:
        df_conv = pd.read_sql_query("SELECT id, contact_id, primary_intent, started_at FROM conversations ORDER BY started_at DESC LIMIT 5", conn)
        print(df_conv)
    except Exception as e:
        print(e)

    conn.close()

if __name__ == "__main__":
    inspect_db()
