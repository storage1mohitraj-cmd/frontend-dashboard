import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

uri = os.getenv('MONGO_URI')
client = MongoClient(uri)

print("Databases available:")
for db_name in client.list_database_names():
    print(f"- {db_name}")
    db = client[db_name]
    for coll in db.list_collection_names():
        if coll == 'auto_redeem_members':
            print(f"  * FOUND auto_redeem_members in {db_name}")
