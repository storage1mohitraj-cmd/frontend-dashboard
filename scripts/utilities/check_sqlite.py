import sqlite3
import os

db_path = "f:/Whiteout Survival Bot/db/settings.sqlite"
if not os.path.exists(db_path):
    print("Database not found")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute("SELECT id, admin, alliances_id FROM adminserver")
        rows = c.fetchall()
        print("--- SQLite adminserver table ---")
        for r in rows:
            print(f"Server ID: {r[0]}, Admin: {r[1]}, Alliance: {r[2]}")
    except Exception as e:
        print(f"Error: {e}")
    conn.close()
