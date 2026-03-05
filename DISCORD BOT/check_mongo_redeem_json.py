import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
import json

load_dotenv()

def check_redeem():
    uri = os.getenv('MONGO_URI')
    if not uri: return

    client = MongoClient(uri)
    db_name = os.getenv('MONGO_DB_NAME', 'reminderbot')
    db = client[db_name]
    coll = db['auto_redeem_members']
    
    guilds = coll.distinct('guild_id')
    results = []
    for gid in guilds:
        m_count = coll.count_documents({'guild_id': gid})
        results.append({'gid': str(gid), 'cnt': m_count})
    
    # Sort by count descending
    results.sort(key=lambda x: x['cnt'], reverse=True)
    print(json.dumps(results))

if __name__ == "__main__":
    check_redeem()
