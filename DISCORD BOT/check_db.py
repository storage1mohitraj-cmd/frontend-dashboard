import sqlite3
import os

db_path = os.path.expanduser('~/app/bot/DISCORD BOT/db/giftcode.sqlite')
print(f"Checking DB at: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check columns
    c.execute("PRAGMA table_info(gift_codes)")
    columns = [col[1] for col in c.fetchall()]
    print(f"Columns in gift_codes: {columns}")
    
    # Check for RamadanJoy2026
    c.execute("SELECT * FROM gift_codes WHERE giftcode='RamadanJoy2026'")
    row = c.fetchone()
    if row:
        print(f"RamadanJoy2026 found: {row}")
    else:
        print("RamadanJoy2026 NOT found in DB")
        c.execute("SELECT count(*) FROM gift_codes")
        count = c.fetchone()[0]
        print(f"Total codes in DB: {count}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
