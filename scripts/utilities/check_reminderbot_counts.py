from pymongo import MongoClient
import certifi

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
client = MongoClient(URI_MAIN, tlsCAFile=certifi.where())
db = client['reminderbot']

print("--- Current reminderbot Status ---")
colls = db.list_collection_names()
for coll in sorted(colls):
    print(f"- {coll}: {db[coll].count_documents({})} docs")

# Check for GTACAT specifically
if "alliance_members" in colls:
    gta_count = db["alliance_members"].count_documents({"alliance": "GTACAT"})
    print(f"\nGTACAT members: {gta_count}")
