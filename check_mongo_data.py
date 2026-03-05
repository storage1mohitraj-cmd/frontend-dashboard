from pymongo import MongoClient
try:
    import certifi
    ca = certifi.where()
except ImportError:
    ca = None

def check_cluster(uri, name):
    print(f"\n--- Checking Cluster: {name} ---")
    try:
        client = MongoClient(uri, tlsCAFile=ca, serverSelectionTimeoutMS=5000)
        dbs = client.list_database_names()
        print(f"Available Databases: {dbs}")
        for db_name in dbs:
            if db_name in ['admin', 'local', 'config']: continue
            db = client[db_name]
            colls = db.list_collection_names()
            print(f" DB: {db_name} ({len(colls)} collections)")
            for coll_name in colls:
                count = db[coll_name].count_documents({})
                print(f"  - {coll_name}: {count} docs")
    except Exception as e:
        print(f" Error: {e}")

URI_REMINDER = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
URI_WOSBOT = "mongodb+srv://yourbook444362_db_user:3KAXZB6hkJ1DAWPT@wosbot.yal4g3b.mongodb.net/?appName=WOSBOT"

check_cluster(URI_REMINDER, "REMINDER")
check_cluster(URI_WOSBOT, "WOSBOT")
