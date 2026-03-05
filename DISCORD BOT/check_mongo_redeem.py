import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
import json

load_dotenv()

def check_redeem():
    uri = os.getenv('MONGO_URI')
    if not uri:
        print("MONGO_URI not set")
        return

    client = MongoClient(uri)
    db_name = os.getenv('MONGO_DB_NAME', 'reminderbot')
    db = client[db_name]
    coll = db['auto_redeem_members']
    
    count = coll.count_documents({})
    print(f"Total members in auto_redeem_members: {count}")
    
    # Check for grouped structure (common source of "empty" perception if not parsed correctly)
    grouped_count = coll.count_documents({'members': {'$exists': True}})
    print(f"Documents with grouped 'members' list: {grouped_count}")
    
    # Sample a few guilds
    guilds = coll.distinct('guild_id')
    print(f"Unique guild IDs found: {len(guilds)}")
    for gid in guilds[:5]:
        m_count = coll.count_documents({'guild_id': gid})
        print(f" Guild {gid}: {m_count} entries")

if __name__ == "__main__":
    check_redeem()
