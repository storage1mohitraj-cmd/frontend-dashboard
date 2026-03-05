import os
from pymongo import MongoClient
import certifi

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
client = MongoClient(URI_MAIN, tlsCAFile=certifi.where())

all_members = list(client["wos_bot"]["alliance_members"].find())
alliance_id = 6

try:
    members = [m for m in all_members if int(m.get('alliance') or m.get('alliance_id') or 0) == alliance_id]
    print(f"Success with modified logic: Found {len(members)} members")

    # Let's test the original logic exactly as written in bot_operations.py
    print("Testing original logic...")
    members = [m for m in all_members if int(m.get('alliance', 0) or m.get('alliance_id', 0)) == alliance_id]
    print(f"Success with original logic: Found {len(members)} members")
except Exception as e:
    print(f"Error thrown in original logic: {type(e).__name__}: {e}")

    for idx, m in enumerate(all_members):
        try:
            val1 = m.get('alliance', 0)
            val2 = m.get('alliance_id', 0)
            res = val1 or val2
            int(res)
        except Exception as ex:
            print(f"Faulty record at index {idx}: _id={m.get('_id')}")
            print(f"alliance={repr(val1)}, alliance_id={repr(val2)}")
            print(f"res={repr(res)} -> int(res) failed with {ex}")
            break
