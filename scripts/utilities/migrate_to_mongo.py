"""
MongoDB Migration Script - Upload SQLite data to MongoDB
Run this on the server where MongoDB is accessible
"""

import sqlite3
import os
from pymongo import MongoClient
from datetime import datetime

def migrate_to_mongodb(mongo_uri):
    """Migrate all SQLite data to MongoDB"""
    
    # Connect to MongoDB
    client = MongoClient(mongo_uri)
    db = client['wos_bot']  # Use 'wos_bot' database
    
    print("[MIGRATION] Starting MongoDB migration...")
    
    # Migrate users/alliance data
    try:
        conn = sqlite3.connect('db/users.sqlite')
        c = conn.cursor()
        c.execute("SELECT fid, nickname, furnace_lv, kid, stove_lv_content, alliance FROM users")
        
        users_collection = db['alliance_members']
        users_collection.delete_many({})  # Clear old data
        
        for row in c.fetchall():
            doc = {
                'fid': row[0],
                'nickname': row[1],
                'furnace_level': row[2],
                'kid': row[3],
                'stove_levels': row[4],
                'alliance': row[5],
                'migrated_at': datetime.utcnow()
            }
            users_collection.insert_one(doc)
        
        count = users_collection.count_documents({})
        print(f"[OK] Migrated {count} alliance members to MongoDB")
        
        conn.close()
    except Exception as e:
        print(f"[ERROR] Error migrating users: {e}")
    
    # Migrate giftcode data
    try:
        conn = sqlite3.connect('db/giftcode.sqlite')
        c = conn.cursor()
        c.execute("SELECT giftcode, date FROM gift_codes")
        
        codes_collection = db['gift_codes']
        codes_collection.delete_many({})
        
        for giftcode, date in c.fetchall():
            doc = {
                'code': giftcode,
                'date': date,
                'migrated_at': datetime.utcnow()
            }
            codes_collection.insert_one(doc)
        
        count = codes_collection.count_documents({})
        print(f"[OK] Migrated {count} gift codes to MongoDB")
        
        conn.close()
    except Exception as e:
        print(f"[ERROR] Error migrating giftcodes: {e}")
    
    client.close()
    print("[MIGRATION] Complete!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python migrate_to_mongo.py <MONGO_URI>")
        print("Example: python migrate_to_mongo.py mongodb+srv://user:pass@cluster.mongodb.net/dbname")
        sys.exit(1)
    
    mongo_uri = sys.argv[1]
    migrate_to_mongodb(mongo_uri)
