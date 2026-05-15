"""
Database Migration Tool - SQLite to MongoDB
Migrate all your local SQLite data to MongoDB for Render persistence
"""

import sqlite3
import os
from datetime import datetime

def backup_databases():
    """Create backups of all SQLite databases"""
    db_dir = 'db'
    backup_dir = 'db/backups'
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    db_files = [
        'alliance.sqlite',
        'users.sqlite',
        'giftcode.sqlite',
        'settings.sqlite',
        'changes.sqlite',
    ]
    
    for db_file in db_files:
        src = os.path.join(db_dir, db_file)
        if os.path.exists(src):
            dst = os.path.join(backup_dir, f"{db_file}.{timestamp}.backup")
            with open(src, 'rb') as f_in:
                with open(dst, 'wb') as f_out:
                    f_out.write(f_in.read())
            print(f"[OK] Backed up {db_file} → {dst}")

def export_alliance_data():
    """Export alliance member data from SQLite"""
    try:
        conn = sqlite3.connect('db/users.sqlite')
        c = conn.cursor()
        
        c.execute("SELECT fid, nickname, furnace_lv, kid, stove_lv_content, alliance FROM users")
        users = c.fetchall()
        
        print(f"\n[ALLIANCE DATA]")
        print(f"Found {len(users)} alliance members:")
        for user in users:
            fid, nickname, furnace_lv, kid, stove_lv, alliance = user
            print(f"  - FID:{fid} | {nickname} | Furnace:{furnace_lv} | Alliance:{alliance}")
        
        conn.close()
        return users
        
    except Exception as e:
        print(f"Error exporting alliance data: {e}")
        return []

def export_giftcode_data():
    """Export giftcode data from SQLite"""
    try:
        conn = sqlite3.connect('db/giftcode.sqlite')
        c = conn.cursor()
        
        c.execute("SELECT giftcode, date FROM gift_codes")
        codes = c.fetchall()
        
        print(f"\n[GIFTCODE DATA]")
        print(f"Found {len(codes)} gift codes:")
        for code, date in codes[:10]:  # Show first 10
            print(f"  - {code} ({date})")
        if len(codes) > 10:
            print(f"  ... and {len(codes) - 10} more")
        
        conn.close()
        return codes
        
    except Exception as e:
        print(f"Error exporting giftcode data: {e}")
        return []

def create_mongo_migration_script():
    """Generate a script to upload data to MongoDB"""
    
    script = '''"""
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
    db = client.get_database()
    
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
'''
    
    with open('migrate_to_mongo.py', 'w', encoding='utf-8') as f:
        f.write(script)
    
    print("[OK] Created migrate_to_mongo.py script")

if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE MIGRATION TOOL - SQLite to MongoDB")
    print("=" * 60)
    
    # Step 1: Backup
    print("\n[STEP 1] Creating backups of all databases...")
    backup_databases()
    
    # Step 2: Export data
    print("\n[STEP 2] Exporting data...")
    alliance_data = export_alliance_data()
    giftcode_data = export_giftcode_data()
    
    # Step 3: Create migration script
    print("\n[STEP 3] Creating MongoDB migration script...")
    create_mongo_migration_script()
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Run: python migrate_to_mongo.py <YOUR_MONGO_URI>")
    print("   Get MONGO_URI from environment variable or MongoDB Atlas")
    print("\n2. Your data will be persisted in MongoDB")
    print("3. On Render, set MONGO_URI environment variable")
    print("4. Bot will use MongoDB instead of ephemeral SQLite")
    print("\n" + "=" * 60)
