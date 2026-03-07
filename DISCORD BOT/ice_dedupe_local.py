import os
import sys
from pymongo import MongoClient
import json
from datetime import datetime

MONGO_URI = 'mongodb+srv://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@reminderbot.r6hso.mongodb.net/?retryWrites=true&w=majority&appName=WOSBOT'
MONGO_WOS_URI = 'mongodb+srv://admin:Magnus123@cluster0.p8vbe.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'

def dedup_ice():
    client_main = MongoClient(MONGO_URI)
    db_main = client_main['reminderbot']
    
    try:
        client_wos = MongoClient(MONGO_WOS_URI)
        db_wos = client_wos['reminderbot']
    except Exception:
        db_wos = None
        
    alliance = db_main['alliance__alliance_list'].find_one({'name': 'ICE'})
    if not alliance:
        print('ICE alliance not found')
        return
        
    guild_id = alliance.get('discord_server_id')
    print(f'Guild ID: {guild_id}')
    search_gid = [int(guild_id), str(guild_id)]
    
    unique_fids = {}
    total_docs_found = 0
    docs_to_delete = []
    
    # Target databases to check
    dbs = [db_main]
    if db_wos:
        dbs.append(db_wos)
        
    for db in dbs:
        print(f"\\nChecking DB: {db.client.address}")
        coll = db['auto_redeem_members']
        docs = list(coll.find({'guild_id': {'$in': search_gid}}))
        total_docs_found += len(docs)
        print(f"Found {len(docs)} documents.")
        
        for doc in docs:
            doc_id = doc['_id']
            # Fallback format checking
            if 'fid' in doc and doc['fid'] and str(doc['fid']).lower() != 'none':
                fid = str(doc['fid']).strip()
                if fid not in unique_fids:
                    unique_fids[fid] = doc
                else:
                    docs_to_delete.append((coll, doc_id))
            elif 'members' in doc and isinstance(doc['members'], list):
                # Has old nested structure
                for m in doc['members']:
                    mfid = m.get('fid')
                    if mfid and str(mfid).lower() != 'none':
                        mfid = str(mfid).strip()
                        if mfid not in unique_fids:
                            unique_fids[mfid] = {
                                'guild_id': int(guild_id),
                                'fid': mfid,
                                'nickname': str(m.get('nickname', 'Unknown')),
                                'furnace_lv': int(m.get('furnace_lv', 0)),
                                'avatar_image': m.get('avatar_image', ''),
                                'added_by': int(m.get('added_by', 0)),
                                'added_at': m.get('added_at', datetime.utcnow().isoformat())
                            }
                docs_to_delete.append((coll, doc_id))

    print(f"\\nSummary:\\nTotal parsed: {total_docs_found} documents")
    print(f"Unique FIDs identified: {len(unique_fids)}")
    print(f"Duplicate documents to clean up: {len(docs_to_delete)}")
    
    if len(unique_fids) == 0:
        print("No valid members found to keep. Exiting.")
        return
        
    total_deleted = 0
    for coll, doc_id in docs_to_delete:
        res = coll.delete_one({'_id': doc_id})
        total_deleted += res.deleted_count
    print(f"Successfully deleted {total_deleted} duplicate/legacy documents.")
    
    coll_main = db_main['auto_redeem_members']
    upserted_count = 0
    updated_count = 0
    for fid, data in unique_fids.items():
        data.pop('_id', None)
        res = coll_main.update_one(
            {'guild_id': int(guild_id), 'fid': str(fid)},
            {'$set': data},
            upsert=True
        )
        if res.upserted_id: upserted_count += 1
        elif res.modified_count > 0: updated_count += 1
        
    print(f"Re-inserted unique members: {upserted_count} new, {updated_count} updated.")
    
if __name__ == '__main__':
    dedup_ice()
