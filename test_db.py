import asyncio, motor.motor_asyncio, os
from dotenv import load_dotenv
load_dotenv()
async def run():
    db = motor.motor_asyncio.AsyncIOMotorClient(os.getenv('MONGO_URI'))['bot_db']
    docs = await db['id_channels'].find().to_list(None)
    print(docs)
asyncio.run(run())
