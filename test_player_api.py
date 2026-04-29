import asyncio
import aiohttp
import time
import hashlib
import ssl

async def test_api(player_id):
    url = "https://wos-giftcode-api.centurygame.com/api/player"
    secret = "tB87#kPtkxqOS2"
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://wos-giftcode.centurygame.com",
    }

    current_time = int(time.time())
    form = f"fid={player_id}&time={current_time}"
    sign = hashlib.md5((form + secret).encode("utf-8")).hexdigest()
    payload = f"sign={sign}&{form}"

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        async with session.post(url, data=payload, headers=headers, timeout=20) as resp:
            print("Status:", resp.status)
            print("Response:", await resp.text())

if __name__ == "__main__":
    asyncio.run(test_api("493761636"))
