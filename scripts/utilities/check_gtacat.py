from pymongo import MongoClient
try:
    import certifi
    ca = certifi.where()
except ImportError:
    ca = None

def check_gtacat(uri, db_name):
    print(f"\n--- Checking for GTACAT/GTA in {db_name} ---")
    client = MongoClient(uri, tlsCAFile=ca, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    
    terms = ["GTACAT", "GTA", "3063"]
    colls = ["alliance_members", "alliance__alliance_list", "alliances", "server_alliances"]
    
    for coll in colls:
        if coll not in db.list_collection_names(): continue
        print(f"\nCollection: {coll}")
        for term in terms:
            count = db[coll].count_documents({
                "$or": [
                    {"name": {"$regex": term, "$options": "i"}},
                    {"alliance": {"$regex": term, "$options": "i"}},
                    {"alliance_name": {"$regex": term, "$options": "i"}},
                    {"nickname": {"$regex": term, "$options": "i"}},
                    {"fid": {"$regex": term, "$options": "i"}}
                ]
            })
            print(f"  Matches for '{term}': {count}")
            if count > 0:
                sample = db[coll].find_one({
                    "$or": [
                        {"name": {"$regex": term, "$options": "i"}},
                        {"alliance": {"$regex": term, "$options": "i"}},
                        {"alliance_name": {"$regex": term, "$options": "i"}},
                        {"nickname": {"$regex": term, "$options": "i"}},
                        {"fid": {"$regex": term, "$options": "i"}}
                    ]
                })
                print(f"    Sample: {sample.get('name') or sample.get('alliance') or sample.get('alliance_name')} (ID: {sample.get('_id')})")

URI_REMINDER = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
check_gtacat(URI_REMINDER, "reminderbot")
