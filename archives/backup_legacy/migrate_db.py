
import sqlite3
import os

db_path = r"f:\STARK-whiteout survival bot\DISCORD BOT\db\giftcode.sqlite"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    # Try alternate location
    db_path = "db/giftcode.sqlite"

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Check if column exists
    c.execute("PRAGMA table_info(gift_codes)")
    columns = [row[1] for row in c.fetchall()]
    print(f"Table columns: {columns}")
    if 'added_at' not in columns:
        c.execute("ALTER TABLE gift_codes ADD COLUMN added_at TEXT")
        print("Added column added_at to gift_codes")
    else:
        print("Column added_at already exists")
    conn.commit()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
