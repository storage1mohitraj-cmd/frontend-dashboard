import sys

sys.stdout.reconfigure(line_buffering=True)
print(">>> [START] Sync script started")

try:
    print(">>> [INIT] Importing Mongo settings...")
    from db.mongo_adapters import _get_db, AutoRedeemMembersAdapter
    print(">>> [INIT] Imports successful.")
except Exception as e:
    print(f">>> [ERROR] Failed on imports: {e}")
    sys.exit(1)

def run_cleanup():
    try:
        print(">>> [DB] Attempting to connect to MongoDB (_get_db)...")
        db_main = _get_db()
        print(">>> [DB] Client connected.")
        
        print(">>> [QUERY] Looking for ICE alliance...")
        alliance = db_main['alliance__alliance_list'].find_one({'name': 'ICE'})
        
        if not alliance:
            print('>>> [ERROR] ICE alliance not found')
            return
            
        guild_id = alliance.get('discord_server_id')
        print(f">>> [VARS] Found ICE Server ID: {guild_id}")
        
        search_gid = [int(guild_id), str(guild_id)]
        unique_members_data = {}
        docs_to_delete = []
        total_found = 0
        
        print(">>> [FETCH] Getting target DB clusters...")
        dbs = AutoRedeemMembersAdapter._get_target_dbs()
        print(f">>> [FETCH] Found {len(dbs)} clusters.")
        
        for idx, db in enumerate(dbs):
            print(f">>> [ITER] Checking cluster #{idx}: {db.name}")
            coll = db['auto_redeem_members']
            print(">>> [ITER] Querying auto_redeem_members for ICE records...")
            # We enforce list to block and fetch everything synchronously
            docs = list(coll.find({'guild_id': {'$in': search_gid}}))
            total_found += len(docs)
            print(f">>> [ITER] Found {len(docs)} documents in {db.name}")
            
            for doc in docs:
                doc_id = doc['_id']
                if 'fid' in doc and doc['fid'] and str(doc['fid']).lower() != 'none':
                    fid = str(doc['fid']).strip()
                    if fid not in unique_members_data:
                        unique_members_data[fid] = doc
                    else:
                        docs_to_delete.append((db.name, doc_id))
                elif 'members' in doc and isinstance(doc['members'], list):
                    for m in doc['members']:
                        mfid = m.get('fid')
                        if mfid and str(mfid).lower() != 'none':
                            mfid = str(mfid).strip()
                            if mfid not in unique_members_data:
                                unique_members_data[mfid] = {
                                    'guild_id': int(guild_id),
                                    'fid': mfid,
                                    'nickname': m.get('nickname', 'Unknown'),
                                    'furnace_lv': int(m.get('furnace_lv', 0))
                                }
                    docs_to_delete.append((db.name, doc_id))

        print(f">>> [RESULTS] Parsed {total_found} entries. Identified {len(unique_members_data)} unique FIDs.")
        print(f">>> [RESULTS] Docs to purge: {len(docs_to_delete)}")
        
        if docs_to_delete:
            print(">>> [ACTION] Deleting duplicates...")
            deleted = 0
            for db_name, doc_id in docs_to_delete:
                for d in AutoRedeemMembersAdapter._get_target_dbs():
                    if d.name == db_name:
                        res = d['auto_redeem_members'].delete_one({'_id': doc_id})
                        deleted += res.deleted_count
                        break
            print(f">>> [ACTION] Successfully deleted {deleted} items.")
            
            print(">>> [ACTION] Upserting unique list back into primary DB...")
            main_coll = db_main['auto_redeem_members']
            upserted = 0
            for fid, data in unique_members_data.items():
                data.pop('_id', None)
                res = main_coll.update_one(
                    {'guild_id': int(guild_id), 'fid': str(fid)},
                    {'$set': data},
                    upsert=True
                )
                if res.upserted_id or res.modified_count > 0:
                    upserted += 1
            print(f">>> [ACTION] Successfully wrote {upserted} true ICE members.")
            
        print(">>> [DONE] ICE Alliance Deduplication complete.")
    except Exception as e:
        print(f">>> [CRASH] Fatal exception in cleanup: {e}")

if __name__ == '__main__':
    print(">>> [BOOT] Loading .env")
    from dotenv import load_dotenv
    load_dotenv()
    print(">>> [BOOT] Loaded.")
    run_cleanup()
