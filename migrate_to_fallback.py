import os
from pymongo import MongoClient
import certifi

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
URI_FALLBACK = "mongodb+srv://yourbook444362_db_user:3KAXZB6hkJ1DAWPT@wosbot.yal4g3b.mongodb.net/?appName=WOSBOT"

print("Connecting to Main and Fallback clusters...")
client_main = MongoClient(URI_MAIN, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
client_fallback = MongoClient(URI_FALLBACK, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)

db_main = client_main["wos_bot"]
db_fallback = client_fallback["wos_bot"]

collections_to_migrate = [
    "alliance_members",
    "furnace_history",
    "gift_codes"
]

for coll_name in collections_to_migrate:
    print(f"\nMigrating collection: {coll_name}...")
    docs = list(db_main[coll_name].find())
    
    if not docs:
        print(f"No documents found in {coll_name} on Main cluster.")
        continue

    # Insert into fallback cluster
    try:
        # Use ordered=False to continue inserting even if some duplicates exist
        result = db_fallback[coll_name].insert_many(docs, ordered=False)
        print(f"Successfully migrated {len(result.inserted_ids)} documents to {coll_name} on Fallback cluster.")
    except Exception as e:
        # If there are duplicates, it will throw a BulkWriteError but still insert the rest
        if hasattr(e, 'details') and 'nInserted' in e.details:
            print(f"Migrated {e.details['nInserted']} new documents to {coll_name} (skipped some duplicates).")
        else:
            print(f"Error during migration for {coll_name}: {e}")

print("\n--- NEW COUNTS IN FALLBACK CLUSTER ---")
for coll_name in collections_to_migrate:
    count = db_fallback[coll_name].count_documents({})
    print(f"{coll_name}: {count}")

print("\nDone!")
