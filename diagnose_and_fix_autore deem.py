#!/usr/bin/env python3
"""
Auto-Redeem Member Diagnostic & Sync Script
Helps diagnose and fix missing auto-redeem members in Oracle VM deployments
"""

import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def get_db_connection(db_name: str, **kwargs):
    """Get SQLite connection"""
    db_path = Path(__file__).parent / 'db' / db_name
    return sqlite3.connect(str(db_path), **kwargs)

def get_mongo_db():
    """Try to get MongoDB connection"""
    try:
        from db.mongo_adapters import _get_db, mongo_enabled
        if mongo_enabled():
            return _get_db(), True
        return None, False
    except Exception as e:
        print(f"❌ Failed to import MongoDB adapter: {e}")
        return None, False

def check_sqlite_members():
    """Check auto-redeem members in SQLite"""
    try:
        conn = get_db_connection('giftcode.sqlite')
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='auto_redeem_members'
        """)
        
        if not cursor.fetchone():
            print("❌ Table 'auto_redeem_members' does not exist in SQLite")
            return []
        
        # Get all members
        cursor.execute("""
            SELECT guild_id, fid, nickname, furnace_lv, avatar_image, added_by, added_at
            FROM auto_redeem_members
            ORDER BY guild_id, added_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ Error querying SQLite: {e}")
        return []

def check_mongodb_members():
    """Check auto-redeem members in MongoDB"""
    try:
        db, enabled = get_mongo_db()
        if not enabled:
            print("⚠️  MongoDB is not enabled (MONGO_URI not set)")
            return None, []
        
        if not db:
            print("⚠️  Could not connect to MongoDB")
            return None, []
        
        coll = db['auto_redeem_members']
        docs = list(coll.find({}))
        return db, docs
    except Exception as e:
        print(f"❌ Error querying MongoDB: {e}")
        return None, []

def diagnose():
    """Run diagnostics"""
    print("=" * 70)
    print("AUTO-REDEEM MEMBER DIAGNOSTIC REPORT")
    print("=" * 70)
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    # Check SQLite
    print("📊 SQLite Database Check")
    print("-" * 70)
    sqlite_members = check_sqlite_members()
    
    if sqlite_members:
        print(f"✅ Found {len(sqlite_members)} members in SQLite")
        
        # Count by guild
        guild_counts = {}
        for row in sqlite_members:
            guild_id = row[0]
            guild_counts[guild_id] = guild_counts.get(guild_id, 0) + 1
        
        print(f"\n   Members by Guild:")
        for guild_id, count in sorted(guild_counts.items()):
            print(f"   - Guild {guild_id}: {count} members")
        
        # Show sample members
        print(f"\n   Sample members (first 5):")
        for i, row in enumerate(sqlite_members[:5], 1):
            guild_id, fid, nickname, furnace_lv, avatar, added_by, added_at = row
            valid_fid = "✅" if fid and str(fid).strip() and str(fid).lower() != 'none' else "❌"
            print(f"   {i}. {valid_fid} FID: {fid}, Guild: {guild_id}, Nickname: {nickname}")
    else:
        print("❌ No members found in SQLite (or table doesn't exist)")
    
    # Check MongoDB
    print("\n📊 MongoDB Database Check")
    print("-" * 70)
    db, mongodb_members = check_mongodb_members()
    
    if db is None:
        print("⚠️  MongoDB connection unavailable or disabled")
    elif mongodb_members:
        print(f"✅ Found {len(mongodb_members)} members in MongoDB")
        
        # Count by guild
        guild_counts = {}
        for doc in mongodb_members:
            guild_id = doc.get('guild_id')
            guild_counts[guild_id] = guild_counts.get(guild_id, 0) + 1
        
        print(f"\n   Members by Guild:")
        for guild_id, count in sorted(guild_counts.items()):
            print(f"   - Guild {guild_id}: {count} members")
    else:
        print("ℹ️  MongoDB is enabled but has no auto-redeem members")
    
    # Data sync status
    print("\n📊 Sync Status Check")
    print("-" * 70)
    
    if sqlite_members and db:
        sqlite_fids = {(row[0], row[1]) for row in sqlite_members if row[1]}
        mongo_fids = {(doc.get('guild_id'), doc.get('fid')) for doc in mongodb_members if doc.get('fid')}
        
        in_sqlite_only = sqlite_fids - mongo_fids
        in_mongo_only = mongo_fids - sqlite_fids
        in_both = sqlite_fids & mongo_fids
        
        print(f"Members in SQLite only: {len(in_sqlite_only)}")
        if in_sqlite_only:
            for guild_id, fid in list(in_sqlite_only)[:5]:
                print(f"  - Guild {guild_id}: {fid}")
        
        print(f"Members in MongoDB only: {len(in_mongo_only)}")
        if in_mongo_only:
            for guild_id, fid in list(in_mongo_only)[:5]:
                print(f"  - Guild {guild_id}: {fid}")
        
        print(f"Members in both: {len(in_both)}")
        
        if in_sqlite_only:
            print("\n⚠️  ISSUE DETECTED: Members in SQLite but not in MongoDB")
            print("    These members won't show up in auto-redeem list!")
            print("    → Run 'python diagnose_and_fix_autore deem.py sync' to fix")
    
    print("\n" + "=" * 70)

def sync_sqlite_to_mongo():
    """Sync members from SQLite to MongoDB"""
    print("=" * 70)
    print("AUTO-REDEEM MEMBER SYNC OPERATION")
    print("=" * 70)
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    # Get SQLite members
    print("📋 Reading members from SQLite...")
    sqlite_members = check_sqlite_members()
    
    if not sqlite_members:
        print("❌ No members to sync from SQLite")
        return 0
    
    print(f"✅ Found {len(sqlite_members)} potential members to sync")
    
    # Get MongoDB connection
    print("\n📋 Connecting to MongoDB...")
    db, enabled = get_mongo_db()
    
    if not enabled:
        print("❌ MongoDB is not enabled. Cannot proceed with sync.")
        print("   Set MONGO_URI environment variable to enable MongoDB")
        return 0
    
    if not db:
        print("❌ Could not connect to MongoDB")
        return 0
    
    print("✅ Connected to MongoDB")
    
    # Sync members
    print("\n📋 Syncing members...")
    sync_count = 0
    error_count = 0
    skip_count = 0
    
    try:
        from db.mongo_adapters import AutoRedeemMembersAdapter
        
        for row in sqlite_members:
            try:
                guild_id, fid, nickname, furnace_lv, avatar_image, added_by, added_at = row
                
                # Skip invalid FIDs
                if not fid or not str(fid).strip() or str(fid).lower() == 'none':
                    skip_count += 1
                    continue
                
                # Check if already exists
                try:
                    if AutoRedeemMembersAdapter.member_exists(guild_id, fid):
                        continue  # Already synced
                except:
                    pass  # Continue attempting sync
                
                # Add to MongoDB
                member_data = {
                    'nickname': nickname or 'Unknown',
                    'furnace_lv': int(furnace_lv or 0),
                    'avatar_image': avatar_image or '',
                    'added_by': int(added_by or 0),
                    'added_at': added_at
                }
                
                success = AutoRedeemMembersAdapter.add_member(guild_id, fid, member_data)
                if success:
                    sync_count += 1
                else:
                    error_count += 1
            except Exception as e:
                print(f"   ⚠️  Error syncing {fid}: {e}")
                error_count += 1
    
    except Exception as e:
        print(f"❌ Failed to sync members: {e}")
        return 0
    
    # Summary
    print("\n" + "=" * 70)
    print("SYNC SUMMARY")
    print("=" * 70)
    print(f"✅ Successfully synced: {sync_count}")
    print(f"❌ Errors: {error_count}")
    print(f"⏭️  Skipped (invalid FIDs): {skip_count}")
    print(f"📊 Total processed: {sync_count + error_count + skip_count} / {len(sqlite_members)}")
    print("=" * 70)
    
    return sync_count

def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'sync':
        print("🔄 SYNC MODE")
        sync_count = sync_sqlite_to_mongo()
        if sync_count > 0:
            print(f"\n✅ Successfully synced {sync_count} members to MongoDB!")
            print("   Auto-redeem members should now appear in the Discord bot")
    else:
        print("🔍 DIAGNOSTIC MODE")
        diagnose()
        print("\nTo sync members from SQLite to MongoDB, run:")
        print("   python diagnose_and_fix_autore deem.py sync")

if __name__ == '__main__':
    main()
