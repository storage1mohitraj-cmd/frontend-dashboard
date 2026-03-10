import aiohttp
import asyncio
import hashlib
import time
import ssl

async def test_api():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        current_time = int(time.time() * 1000)
        fid = '467650890'
        secret = 'tB87#kPtkxqOS2'
        form = f'fid={fid}&time={current_time}'
        sign = hashlib.md5((form + secret).encode('utf-8')).hexdigest()
        payload = f'sign={sign}&{form}'

        # Test with different headers
        headers_list = [
            {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://wos-giftcode-api.centurygame.com'
            },
            {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://wos-giftcode-api.centurygame.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': 'https://wos-giftcode-api.centurygame.com'
            }
        ]

        for i, headers in enumerate(headers_list, 1):
            print(f"\nTesting headers set {i}: {headers}")
            try:
                async with session.post('https://wos-giftcode-api.centurygame.com/api/player',
                                      data=payload, headers=headers, timeout=10) as resp:
                    text = await resp.text()
                    print(f'Status: {resp.status}')
                    print(f'Response: {text[:200]}...')
            except Exception as e:
                print(f'Error: {e}')

asyncio.run(test_api())