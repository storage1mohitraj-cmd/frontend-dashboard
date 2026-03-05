import os
from pymongo import MongoClient
import certifi

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
client = MongoClient(URI_MAIN, tlsCAFile=certifi.where())

COLL = 'server_alliances'
print("Testing get_alliance logic across all docs in main db...")

for doc in client["discord_bot"][COLL].find():
    guild_id = doc.get('_id')
    print(f"\n--- Document {guild_id} ---")
    print(doc)
    
    # Simulate the logic
    try:
        val1 = doc.get('alliances_id')
        val2 = doc.get('alliance_id')
        
        # Original logic: int(doc.get('alliances_id') or doc.get('alliance_id'))
        # If val1 is None, it evalulates val2. If both are None, it is `int(None)` which throws TypeError.
        # But wait! If it throws TypeError, get_alliance captures Exception and returns None!
        # This completely masks the error!
        combined = val1 if val1 is not None else val2
        
        if combined is not None:
            print(f"Success: Returns {int(combined)}")
        else:
            print(f"Failed: Returns None (no alliance fields found)")
            
    except Exception as e:
        print(f"Exception masked by get_alliance: {e}")
