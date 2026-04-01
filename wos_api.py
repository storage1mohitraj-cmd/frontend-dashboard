from typing import Optional
import aiohttp
import hashlib
import time
import os
import json
import ssl
import logging

logger = logging.getLogger(__name__)

async def fetch_player_info(player_id: str) -> Optional[dict ]:
    """
    Fetch player info from the WOS giftcode API.
    Returns a dict with keys: id, nickname, level, power, avatar_image, etc.
    Returns None if player not found or error.
    """
    # Use the endpoint that is known to work in playerinfo.py
    url = "https://wos-giftcode-api.centurygame.com/api/player"
    secret = "tB87#kPtkxqOS2"
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://wos-giftcode-api.centurygame.com",
    }

    try:
        current_time = int(time.time() * 1000)
        form = f"fid={player_id}&time={current_time}"
        sign = hashlib.md5((form + secret).encode("utf-8")).hexdigest()
        payload = f"sign={sign}&{form}"

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(url, data=payload, headers=headers, timeout=20) as resp:
                if resp.status != 200:
                    print(f"[ERROR] wos_api: Failed to fetch player info for {player_id}: Status {resp.status}")
                    return None
                
                try:
                    js = await resp.json()
                except Exception:
                    print(f"[ERROR] wos_api: Invalid JSON response for {player_id}")
                    return None

                if js.get("code") == 0:
                    data = js.get("data", {})
                    # Normalize keys to match what callers expect
                    return {
                        "id": data.get("kid"),
                        "name": data.get("nickname"),
                        "level": int(data.get("stove_lv", 0)) if data.get("stove_lv") else 0,
                        "power": data.get("stove_lv_content"), # Using this for stove_lv_content/power mapping
                        "avatar_image": data.get("avatar_image")
                    }
                else:
                    print(f"[ERROR] wos_api: API returned error code {js.get('code')} for {player_id}: {js.get('msg')}")
                    return None

    except Exception as e:
        print(f"[ERROR] wos_api: Exception fetching player info for {player_id}: {e}")
        return None


async def fetch_wos_player(player_id: str) -> Optional[dict]:
    """
    Fetch live WOS player stats in the format used by angel_personality and app.py.
    Returns dict with keys: player_id, nickname, furnace_level, state_id.
    Returns None on failure.
    """
    data = await fetch_player_info(player_id)
    if not data:
        return None
    return {
        "player_id": player_id,
        "nickname": data.get("name", "Unknown"),
        "furnace_level": data.get("level", 0),
        "state_id": str(data.get("id", "N/A")),
    }
