import urllib.request
import json
import os
import sys

print(">>> [INIT] Fetching bot token securely")
token = os.environ.get("DISCORD_TOKEN") or "YOUR_TOKEN_HERE"

if not token:
    print("Token not found!")
    sys.exit(1)

# Connect directly to MongoDB
MONGO_URI = 'mongodb://iammagnusx1_db_user:zYFHUOjjXhfGLpMs@ac-uofhnd3-shard-00-00.r6hso.mongodb.net:27017,ac-uofhnd3-shard-00-01.r6hso.mongodb.net:27017,ac-uofhnd3-shard-00-02.r6hso.mongodb.net:27017/?ssl=true&replicaSet=atlas-2y4jxj-shard-0&authSource=admin&retryWrites=true&w=majority&appName=WOSBOT'
MONGO_WOS_URI = 'mongodb://admin:Magnus123@cluster0-shard-00-00.p8vbe.mongodb.net:27017,cluster0-shard-00-01.p8vbe.mongodb.net:27017,cluster0-shard-00-02.p8vbe.mongodb.net:27017/?ssl=true&replicaSet=atlas-13c5h9-shard-0&authSource=admin&retryWrites=true&w=majority&appName=Cluster0'

import pymongo
client_main = pymongo.MongoClient(MONGO_URI)
db_main = client_main['reminderbot']

try:
    client_wos = pymongo.MongoClient(MONGO_WOS_URI)
    db_wos = client_wos['reminderbot']
except Exception:
    db_wos = None
    
alliance = db_main['alliance__alliance_list'].find_one({'name': 'ICE'})
if not alliance:
    print('ICE alliance not found')
    sys.exit(1)

guild_id = alliance.get('discord_server_id')
search_gid = [int(guild_id), str(guild_id)]

unique_fids = {}
docs_to_delete = []
total_docs_found = 0

dbs = [db_main]
if db_wos:
    dbs.append(db_wos)

for db in dbs:
    coll = db['auto_redeem_members']
    docs = list(coll.find({'guild_id': {'$in': search_gid}}))
    total_docs_found += len(docs)
    
    for doc in docs:
        doc_id = doc['_id']
        if 'fid' in doc and doc['fid'] and str(doc['fid']).lower() != 'none':
            fid = str(doc['fid']).strip()
            if fid not in unique_fids:
                unique_fids[fid] = doc
            else:
                docs_to_delete.append((coll, doc_id))
        elif 'members' in doc and isinstance(doc['members'], list):
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
                            'added_by': int(m.get('added_by', 0))
                        }
            docs_to_delete.append((coll, doc_id))

print(f"Total parsed: {total_docs_found} documents")
print(f"Unique FIDs identified: {len(unique_fids)}")
print(f"Duplicate documents to clean up: {len(docs_to_delete)}")

total_deleted = 0
for coll, doc_id in docs_to_delete:
    res = coll.delete_one({'_id': doc_id})
    total_deleted += res.deleted_count
print(f"Successfully deleted {total_deleted} duplicate/legacy documents.")

# Send Discord API Message
req = urllib.request.Request(
    f"https://discord.com/api/v10/channels/1344445778810798150/messages",
    data=json.dumps({"content": f"✅ Manually removed **{total_deleted}** duplicate entries for the ICE alliance.\nTotal unique remaining members: **{len(unique_fids)}**."}).encode('utf-8'),
    headers={
        'Authorization': f'Bot {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'DiscordBot (https://github.com/Rapptz/discord.py, 2.3.2)'
    },
    method='POST'
)

try:
    with urllib.request.urlopen(req) as resp:
        print("Discord notification sent.")
except Exception as e:
    print(f"Failed to post to Discord: {e}")
