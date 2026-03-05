from pymongo import MongoClient
import certifi

def check_id_13(uri):
    client = MongoClient(uri, tlsCAFile=certifi.where())
    db = client['reminderbot']
    
    print("--- Checking ID 13 across all collections ---")
    for coll_name in db.list_collection_names():
        try:
            # Check for alliance_id: 13, id: 13, or _id: 13
            doc = db[coll_name].find_one({
                "$or": [
                    {"alliance_id": 13},
                    {"id": 13},
                    {"_id": 13},
                    {"alliance_id": "13"},
                    {"id": "13"},
                    {"_id": "13"}
                ]
            })
            if doc:
                print(f"\nCollection: {coll_name}")
                print(f" Document: {doc}")
        except:
            pass

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
check_id_13(URI_MAIN)
