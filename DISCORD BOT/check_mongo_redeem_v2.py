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
    print(f"Total members: {count}")
    
    guilds = coll.distinct('guild_id')
    print(f"Unique guild IDs found: {len(guilds)}")
    
    results = []
    for gid in guilds:
        m_count = coll.count_documents({'guild_id': gid})
        results.append({'guild_id': gid, 'count': m_count})
    
    # Sort by count descending
    results.sort(key=lambda x: x['count'], reverse=True)
    
    for r in results:
        print(f"Guild {r['guild_id']}: {r['count']} members")

if __name__ == "__main__":
    check_redeem()
