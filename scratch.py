
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    db = AsyncIOMotorClient('mongodb://localhost:27017')['wos_bot_main']
    doc = await db.moderation_actions.find_one()
    print(doc)

asyncio.run(main())
