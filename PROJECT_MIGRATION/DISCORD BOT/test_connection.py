"""
Simple script to test Discord bot connection
"""
import discord
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

print(f"Token loaded: {TOKEN[:20]}..." if TOKEN else "No token found!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ Successfully logged in as {client.user}!')
    print(f'Bot ID: {client.user.id}')
    print(f'Connected to {len(client.guilds)} servers')
    await client.close()

print("Attempting to connect to Discord...")
try:
    client.run(TOKEN)
except Exception as e:
    print(f"❌ Connection failed: {e}")
