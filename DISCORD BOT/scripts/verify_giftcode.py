import asyncio
import aiohttp
import hashlib
import time
import json
import ssl
import sys

# Configuration
WOS_GIFTCODE_URL = "https://wos-giftcode-api.centurygame.com/api/gift_code"
WOS_CAPTCHA_URL = "https://wos-giftcode-api.centurygame.com/api/captcha"
WOS_PLAYER_URL = "https://wos-giftcode-api.centurygame.com/api/player"
SECRET_KEY = "tB87#kPtkxqOS2"

async def get_player_info(fid):
    """Fetch player info to validate FID and get session"""
    print(f"Fetching player info for FID: {fid}...")
    current_time = int(time.time() * 1000)
    data = {
        "fid": str(fid),
        "time": str(current_time)
    }
    
    # Sign
    sorted_keys = sorted(data.keys())
    form_parts = [f"{key}={data[key]}" for key in sorted_keys]
    form = "&".join(form_parts)
    sign = hashlib.md5((form + SECRET_KEY).encode('utf-8')).hexdigest()
    payload = f"sign={sign}&{form}"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://wos-giftcode-api.centurygame.com",
        "Referer": "https://wos-giftcode-api.centurygame.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        async with session.post(WOS_PLAYER_URL, data=payload, headers=headers) as resp:
            print(f"Player API Status: {resp.status}")
            text = await resp.text()
            print(f"Player API Response: {text}")
            return session, text

async def test_giftcode(fid, code):
    """Test a gift code"""
    print(f"\nTesting code '{code}' for FID '{fid}'...")
    
    # 1. Get player info first
    try:
        _, player_resp = await get_player_info(fid)
        player_data = json.loads(player_resp)
        if player_data.get('code') != 0:
            print("Failed to get player info. Aborting.")
            return
            
        nickname = player_data.get('data', {}).get('nickname', 'Unknown')
        print(f"Player found: {nickname}")
        
    except Exception as e:
        print(f"Error fetching player: {e}")
        return

    # 2. We can't easily bypass CAPTCHA here without the solver logic.
    # However, we can verify if the code is valid by checking if it exists in the bot's known list 
    # OR we can try to redeem it and see the error.
    # To fully test TIME_ERROR, we need to solve captcha.
    
    print("\nNOTE: Full redemption requires CAPTCHA solving which is complex to run standalone.")
    print("However, 'TIME_ERROR' usually comes from the game server AFTER valid captcha.")
    print("If you want to test specifically for TIME_ERROR, we need to run the bot.")
    print("\nThis script verified that we can connect to the API.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python verify_giftcode.py <FID> <CODE>")
        print("Example: python verify_giftcode.py 12345678 HappyFriday")
        sys.exit(1)
        
    fid = sys.argv[1]
    code = sys.argv[2]
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(test_giftcode(fid, code))
