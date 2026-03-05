import os
from pymongo import MongoClient
import certifi

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
client = MongoClient(URI_MAIN, tlsCAFile=certifi.where())

COLL = 'settings__adminserver'
print(f"--- Dumping {COLL} ---")

for doc in client["discord_bot"][COLL].find():
    print(doc)
    
COLL = 'server_alliances'
print(f"\n--- Dumping {COLL} ---")
for doc in client["discord_bot"][COLL].find():
    print(f"{doc.get('_id')} - pwd: {doc.get('member_list_password')}")
