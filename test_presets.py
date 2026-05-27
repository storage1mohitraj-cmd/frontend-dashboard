import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.get('http://140.245.241.54:3000/api/reminders/presets')
        print(r.status_code)
        print(r.text[:500])

asyncio.run(main())
