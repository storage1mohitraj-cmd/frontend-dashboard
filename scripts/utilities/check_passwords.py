import os
from pymongo import MongoClient
import certifi

URI_FALLBACK = "mongodb+srv://yourbook444362_db_user:3KAXZB6hkJ1DAWPT@wosbot.yal4g3b.mongodb.net/?appName=WOSBOT"
client = MongoClient(URI_FALLBACK, tlsCAFile=certifi.where())

print("--- server_alliances (discord_bot on Fallback Cluster) ---")
for doc in client["discord_bot"]["server_alliances"].find():
    print(doc)
