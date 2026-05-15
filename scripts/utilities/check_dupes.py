import pymongo

uri = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
client = pymongo.MongoClient(uri)
db = client['reminderbot']
collection = db['alliance_members']

members = list(collection.find({"alliance": {"$in": ["1", 1]}}))
print(f"Total members found for Alliance 1: {len(members)}")

seen_nicks = set()
duplicate_nicks = []

for m in members:
    nick = m.get('nickname', '').lower().strip()
    if nick in seen_nicks:
        duplicate_nicks.append(nick)
    else:
        seen_nicks.add(nick)

print(f"Found {len(duplicate_nicks)} duplicate records based on nickname.")
print("Duplicate Nicknames:", duplicate_nicks[:20])
