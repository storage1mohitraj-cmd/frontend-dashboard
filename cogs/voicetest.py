import discord
from discord import app_commands
from discord.ext import commands
import asyncio

class VoiceTest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="voicetest", description="Test standard Discord voice connection (no Lavalink)")
    async def voicetest(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not interaction.user.voice:
            return await interaction.followup.send("You are not in a voice channel!")
            
        channel = interaction.user.voice.channel
        print(f"🧪 [TEST] Attempting standard connection to {channel.name}...")
        
        try:
            # Try to connect using standard discord.py VoiceClient
            # This will use the bot's own network, not Lavalink
            vc = await channel.connect(timeout=20.0, self_deaf=True)
            print(f"🧪 [TEST] Success! Connected to {channel.name}")
            await asyncio.sleep(2)
            await vc.disconnect()
            await interaction.followup.send(f"✅ Standard voice connection successful! (This means the issue is specifically with Lavalink/Wavelink)")
        except Exception as e:
            print(f"🧪 [TEST] Failed! Error: {e}")
            await interaction.followup.send(f"❌ Standard voice connection failed: {e}\n(This means the issue is with the Bot/VM/Discord Gateway, not Lavalink)")

async def setup(bot):
    await bot.add_cog(VoiceTest(bot))
