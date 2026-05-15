import os
from pymongo import MongoClient

URI_MAIN = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
URI_FALLBACK = "mongodb+srv://yourbook444362_db_user:3KAXZB6hkJ1DAWPT@wosbot.y85er.mongodb.net/?appName=wosbot"

def check_db(name, uri):
    print(f"\n==========================================")
    print(f"Checking Connection: {name}")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        dbs = client.list_database_names()
        for db_name in dbs:
            if db_name in ['admin', 'local']: continue
            print(f"\n  Database: {db_name}")
            db = client[db_name]
            cols = db.list_collection_names()
            for col_name in cols:
                count = db[col_name].estimated_document_count()
                if count > 0:
                    print(f"    - Collection '{col_name}': {count} documents")
    except Exception as e:
        print(f"Error: {e}")

check_db("MAIN CLUSTER", URI_MAIN)
check_db("FALLBACK CLUSTER", URI_FALLBACK)
