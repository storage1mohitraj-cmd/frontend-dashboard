from pymongo import MongoClient
import os

def check_db_codes():
    mongo_uri = "mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminder.hlx5aem.mongodb.net/?appName=REMINDER"
    client = MongoClient(mongo_uri)
    db = client.reminderbot
    collection = db.gift_codes
    
    codes = list(collection.find({"_id": {"$regex": "Children", "$options": "i"}}))
    for c in codes:
        print(f"ID: {repr(c['_id'])}")
        print(f"Full Doc: {c}")
        print("-" * 20)

if __name__ == "__main__":
    check_db_codes()
