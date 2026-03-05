import os
from pymongo import MongoClient
import certifi

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
client = MongoClient(URI_MAIN, tlsCAFile=certifi.where())

print("--- server_alliances (discord_bot) ---")
for doc in client["discord_bot"]["server_alliances"].find():
    guild_id = doc.get("_id")
    if not guild_id:
        guild_id = doc.get("guild_id")
    alliance_id = doc.get("alliances_id") or doc.get("alliance_id")
    print(f"Guild: {guild_id}, Alliance ID mapped: {alliance_id}")

print("\n--- DISTINCT alliances in wos_bot.alliance_members ---")
alliances = set()
for doc in client["wos_bot"]["alliance_members"].find():
    a1 = doc.get("alliance")
    a2 = doc.get("alliance_id")
    alliances.add(f"alliance: {a1} (type {type(a1)}), alliance_id: {a2} (type {type(a2)})")

for a in alliances:
    print(a)
