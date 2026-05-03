import discord
from discord.ext import commands, tasks
import asyncio
import os
import random

class RichPresence(commands.Cog):
    """Handles rotating bot statuses (Rich Presence)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.interval = int(os.getenv("ROTATION_INTERVAL_SECONDS", "15"))
        self.invite = os.getenv("PRESENCE_INVITE", "discord.gg/yourinvite")
        self.presence_task.start()
        print(f"✨ Rich Presence cog loaded (Interval: {self.interval}s)")

    def cog_unload(self):
        self.presence_task.cancel()

    @tasks.loop(seconds=15) # Default to 15s as requested
    async def presence_task(self):
        await self.bot.wait_until_ready()
        
        # Calculate dynamic stats
        guild_count = len(self.bot.guilds)
        user_count = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)
        
        # Presence List
        presences = [
            discord.Activity(type=discord.ActivityType.watching, name=f"{guild_count} States ❄️"),
            discord.Activity(type=discord.ActivityType.listening, name=f"Music in {len(self.bot.voice_clients)} VCs 🎵"),
            discord.Activity(type=discord.ActivityType.playing, name=f"Join: {self.invite}"),
            discord.Activity(type=discord.ActivityType.watching, name=f"{user_count} Survivors 🛡️"),
            discord.Activity(type=discord.ActivityType.playing, name="/play <song name>"),
            discord.Activity(type=discord.ActivityType.watching, name="for new Giftcodes 🎁")
        ]
        
        try:
            activity = random.choice(presences)
            await self.bot.change_presence(activity=activity)
        except Exception as e:
            print(f"⚠️ Failed to update presence: {e}")

    @presence_task.before_loop
    async def before_presence(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(RichPresence(bot))
