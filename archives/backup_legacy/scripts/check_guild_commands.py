import re, json, urllib.request, sys
p = r'F:/STARK-whiteout survival bot/DISCORD BOT/.env'
try:
    s = open(p, 'r', encoding='utf-8').read()
except Exception as e:
    print('Failed to read .env:', e)
    sys.exit(1)
mt = re.search(r'^DISCORD_TOKEN=(.+)$', s, flags=re.M)
if not mt:
    print('No DISCORD_TOKEN found in .env')
    sys.exit(1)
token = mt.group(1).strip().strip('"')
mg = re.search(r'^GUILD_ID=(.+)$', s, flags=re.M)
if not mg:
    print('No GUILD_ID found in .env')
    sys.exit(1)
gid = mg.group(1).strip()
print('GUILD_ID=', gid)
url = f'https://discord.com/api/v10/applications/@me/guilds/{gid}/commands'
req = urllib.request.Request(url, headers={'Authorization': f'Bot {token}'})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
        print(json.dumps(data, indent=2))
except Exception as e:
    print('ERROR fetching commands:', e)
    try:
        import traceback
        traceback.print_exc()
    except Exception:
        pass
    sys.exit(1)
