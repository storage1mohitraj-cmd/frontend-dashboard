import os
from pymongo import MongoClient
import certifi

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
URI_FALLBACK = "mongodb+srv://yourbook444362_db_user:3KAXZB6hkJ1DAWPT@wosbot.yal4g3b.mongodb.net/?appName=WOSBOT"

client_main = MongoClient(URI_MAIN, tlsCAFile=certifi.where())

print('--- Active Alliances in discord_bot ---')
for a in client_main['discord_bot']['alliance__alliance_list'].find():
    print(f"{a.get('alliance_id', 'None')}: {a.get('name', 'Unknown')}")

print('\n--- Legacy Alliances in reminderbot ---')
for a in client_main['reminderbot']['alliances'].find():
    print(f"{a.get('alliance_id', 'None')}: {a.get('name', 'Unknown')}")
