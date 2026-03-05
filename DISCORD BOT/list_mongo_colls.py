import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

uri = os.getenv('MONGO_URI')
client = MongoClient(uri)
db_name = os.getenv('MONGO_DB_NAME', 'reminderbot')
db = client[db_name]

print(f"Collections in {db_name}:")
for coll in db.list_collection_names():
    print(f"- {coll}: {db[coll].count_documents({})} documents")
