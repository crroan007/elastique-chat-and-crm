import sqlite3

def verify():
    conn = sqlite3.connect('data/elastique.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts WHERE email = 'test@verify.com'")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        print("SUCCESS: Contact found in DB!")
        print(row)
    else:
        print("FAILURE: Contact NOT found.")

if __name__ == "__main__":
    verify()
