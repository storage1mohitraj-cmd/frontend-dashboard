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

    @tasks.loop(seconds=15)
    async def presence_task(self):
        await self.bot.wait_until_ready()
        
        # Calculate dynamic stats
        guild_count = len(self.bot.guilds)
        user_count = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)
        
        # Presence List
        presences = [
            # DYNAMIC STATS
            discord.Activity(type=discord.ActivityType.watching, name=f"{guild_count} States ❄️"),
            discord.Activity(type=discord.ActivityType.watching, name=f"{user_count} Survivors 🛡️"),

            # AI COMMANDS
            discord.Activity(type=discord.ActivityType.playing, name="🤖 Chat with AI — /ask anything!"),
            discord.Activity(type=discord.ActivityType.watching, name="🎨 Personalize chat — /personalisechat"),
            discord.Activity(type=discord.ActivityType.playing, name="✨ Generate AI art — /imagine"),

            # MUSIC COMMANDS
            discord.Activity(type=discord.ActivityType.listening, name="🎵 Play music — /play [song]"),
            discord.Activity(type=discord.ActivityType.listening, name="⏸️ Control playback — /pause /resume /skip"),
            discord.Activity(type=discord.ActivityType.listening, name="🎼 Manage queue — /queue /shuffle /loop"),
            discord.Activity(type=discord.ActivityType.listening, name="🎚️ Adjust volume — /volume [0-100]"),
            discord.Activity(type=discord.ActivityType.listening, name="📜 View now playing — /nowplaying"),
            discord.Activity(type=discord.ActivityType.listening, name="💾 Save playlists — /playlist"),
            discord.Activity(type=discord.ActivityType.listening, name="⏮️ Previous track — /previous"),
            discord.Activity(type=discord.ActivityType.listening, name="⏩ Seek position — /seek [time]"),
            discord.Activity(type=discord.ActivityType.listening, name="🗑️ Clear queue — /clear"),
            discord.Activity(type=discord.ActivityType.listening, name="❌ Remove track — /remove [position]"),
            discord.Activity(type=discord.ActivityType.listening, name="🛑 Stop music — /stop"),

            # REMINDERS & EVENTS
            discord.Activity(type=discord.ActivityType.playing, name="⏰ Set reminders — /reminder"),
            discord.Activity(type=discord.ActivityType.watching, name="📊 Reminder dashboard — /reminderdashboard"),
            discord.Activity(type=discord.ActivityType.playing, name="🎪 WOS events info — /event"),
            discord.Activity(type=discord.ActivityType.playing, name="🎂 Set birthday — /birthday"),

            # ALLIANCE & GAME COMMANDS
            discord.Activity(type=discord.ActivityType.watching, name="🏰 Alliance monitor — /alliancemonitor"),
            discord.Activity(type=discord.ActivityType.watching, name="📈 Alliance activity — /allianceactivity"),
            discord.Activity(type=discord.ActivityType.watching, name="⚙️ Alliance settings — /settings"),
            discord.Activity(type=discord.ActivityType.playing, name="🔄 Refresh data — /refresh"),
            discord.Activity(type=discord.ActivityType.playing, name="🎮 Player info — check stats"),
            discord.Activity(type=discord.ActivityType.watching, name="📅 Server age — /server_age"),

            # GIFT CODE COMMANDS
            discord.Activity(type=discord.ActivityType.playing, name="🎁 Active gift codes — /giftcode"),
            discord.Activity(type=discord.ActivityType.watching, name="⚙️ Gift code settings — /giftcodesettings"),
            discord.Activity(type=discord.ActivityType.playing, name="🎯 Auto-redeem codes — configure now!"),

            # TRANSLATION COMMANDS
            discord.Activity(type=discord.ActivityType.watching, name="🌐 Auto translate — /autotranslatecreate"),
            discord.Activity(type=discord.ActivityType.watching, name="📝 Translation list — /autotranslatelist"),
            discord.Activity(type=discord.ActivityType.watching, name="✏️ Edit translation — /autotranslateedit"),
            discord.Activity(type=discord.ActivityType.watching, name="🔄 Toggle translation — /autotranslatetoggle"),
            discord.Activity(type=discord.ActivityType.watching, name="🗑️ Delete translation — /autotranslatedelete"),

            # SERVER MANAGEMENT
            discord.Activity(type=discord.ActivityType.watching, name="👋 Welcome messages — /welcome"),
            discord.Activity(type=discord.ActivityType.watching, name="🗑️ Remove welcome — /removewelcomechannel"),
            discord.Activity(type=discord.ActivityType.playing, name="🔧 Manage server — /manage"),
            discord.Activity(type=discord.ActivityType.playing, name="🏠 Main menu — /start"),

            # STATISTICS & INFO
            discord.Activity(type=discord.ActivityType.watching, name="📊 Server stats — /serverstats"),
            discord.Activity(type=discord.ActivityType.watching, name="🔥 Most active users — /mostactive"),
            discord.Activity(type=discord.ActivityType.watching, name="💾 Storage status — /storage_status"),

            # UTILITIES
            discord.Activity(type=discord.ActivityType.playing, name="🔍 Web search — /websearch"),
            discord.Activity(type=discord.ActivityType.playing, name="🎲 Roll dice — /dice"),
            discord.Activity(type=discord.ActivityType.playing, name="⚔️ Dice battle — /dicebattle"),
            discord.Activity(type=discord.ActivityType.watching, name="❓ Help & commands — /help"),

            # HIGHLIGHTS
            discord.Activity(type=discord.ActivityType.playing, name="🌟 Start here — /start menu"),
            discord.Activity(type=discord.ActivityType.listening, name="💬 Ask me anything — /ask"),
            discord.Activity(type=discord.ActivityType.listening, name="🎵 Music player ready — /play"),
            discord.Activity(type=discord.ActivityType.playing, name="⏰ Never miss events — /reminder"),
            discord.Activity(type=discord.ActivityType.playing, name="🎁 Free rewards — /giftcode"),
            discord.Activity(type=discord.ActivityType.watching, name="🏰 Track alliance — /alliancemonitor"),
            discord.Activity(type=discord.ActivityType.playing, name="✨ AI image generator — /imagine"),
            discord.Activity(type=discord.ActivityType.watching, name="🌐 Auto translate chats — setup now!"),
            discord.Activity(type=discord.ActivityType.watching, name="📊 Server insights — /serverstats"),
            discord.Activity(type=discord.ActivityType.watching, name="🤖 Full command list — /help")
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
