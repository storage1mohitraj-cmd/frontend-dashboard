import os
from pymongo import MongoClient
import certifi

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
URI_FALLBACK = "mongodb+srv://yourbook444362_db_user:3KAXZB6hkJ1DAWPT@wosbot.yal4g3b.mongodb.net/?appName=WOSBOT"

def check_db(uri, db_name, label):
    try:
        client = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
        db = client[db_name]
        collections = db.list_collection_names()
        print(f"--- {label} -> Database: {db_name} ---")
        if not collections:
            print("  (Empty Database - No Collections)")
        for coll in collections:
            count = db[coll].count_documents({})
            print(f"  {coll}: {count} records")
        print("")
    except Exception as e:
        print(f"Error connecting to {label} ({db_name}): {e}\n")

print("Checking data in Main Cluster (reminder.hlx5aem)...")
check_db(URI_MAIN, "discord_bot", "Main Cluster")
check_db(URI_MAIN, "whiteout_survival_bot", "Main Cluster")
check_db(URI_MAIN, "wos_bot", "Main Cluster")

print("Checking data in Fallback Cluster (wosbot.yal4g3b)...")
check_db(URI_FALLBACK, "wos_bot", "Fallback Cluster")
check_db(URI_FALLBACK, "discord_bot", "Fallback Cluster")
check_db(URI_FALLBACK, "whiteout_survival_bot", "Fallback Cluster")
