import sqlite3

conn = sqlite3.connect('data/elastique.db')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]

output = []
output.append("=" * 50)
output.append("EXISTING TABLES IN elastique.db")
output.append("=" * 50)
for t in sorted(tables):
    cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
    output.append(f"  + {t} ({len(cols)} columns)")

output.append("")
output.append("=" * 50)
output.append("SCHEMA GAPS (Tables NOT yet created)")
output.append("=" * 50)
needed = ['workflows', 'workflow_executions', 'contact_tags', 'email_events', 'email_templates']
for table in needed:
    exists = table in tables
    output.append(f"  {'+ EXISTS' if exists else '- MISSING'}: {table}")

conn.close()

# Write to file
with open('schema_audit.txt', 'w') as f:
    f.write('\n'.join(output))

print("Audit written to schema_audit.txt")
