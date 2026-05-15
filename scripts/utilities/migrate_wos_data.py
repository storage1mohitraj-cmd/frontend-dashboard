import os
from pymongo import MongoClient
import certifi

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"

client = MongoClient(URI_MAIN, tlsCAFile=certifi.where())

db_old = client["discord_bot"]
db_new = client["wos_bot"]

# Let's count before migrating
def print_counts():
    print(f"wos_bot alliance_members: {db_new['alliance_members'].count_documents({})}")
    print(f"wos_bot furnace_history: {db_new['furnace_history'].count_documents({})}")
    print(f"wos_bot gift_codes: {db_new['gift_codes'].count_documents({})}")

print("--- BEFORE MIGRATION ---")
print_counts()

print("\nMigrating data...")

# 1. Migrate alliance_members (upsert by fid)
members_migrated = 0
for doc in db_old["alliance_members"].find():
    fid = doc.get("fid")
    if not fid: continue
    
    # Check if already in new db by fid
    existing = db_new["alliance_members"].find_one({"fid": fid})
    if not existing:
        db_new["alliance_members"].insert_one(doc)
        members_migrated += 1
    else:
        # If the old one has more data, we could update, but lets just skip to avoid overwriting new data
        pass

# 2. Migrate furnace_history (upsert by fid + new_level + change_date)
history_migrated = 0
for doc in db_old["furnace_history"].find():
    query = {
        "fid": doc.get("fid"),
        "new_level": doc.get("new_level"),
        "change_date": doc.get("change_date")
    }
    existing = db_new["furnace_history"].find_one(query)
    if not existing:
        db_new["furnace_history"].insert_one(doc)
        history_migrated += 1

# 3. Migrate gift_codes (upsert by code string)
gifts_migrated = 0
for doc in db_old["gift_codes"].find():
    code = doc.get("_id") or doc.get("code")
    if not code: continue
    existing = db_new["gift_codes"].find_one({"_id": code})
    if not existing:
        try:
            db_new["gift_codes"].insert_one(doc)
            gifts_migrated += 1
        except Exception as e:
            # Handle duplicate key error if _id already exists but wasn't caught
            pass

print(f"\nMigrated {members_migrated} missing alliance members.")
print(f"Migrated {history_migrated} missing furnace history events.")
print(f"Migrated {gifts_migrated} missing gift codes.")

print("\n--- AFTER MIGRATION ---")
print_counts()
