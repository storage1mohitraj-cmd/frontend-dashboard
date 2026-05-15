import pymongo

uri = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
client = pymongo.MongoClient(uri)
db = client['reminderbot']
doc = db['alliance_members'].find_one({'alliance': 1})
if doc:
    print("Keys available:")
    for k in doc.keys():
        print(f"- {k}")
