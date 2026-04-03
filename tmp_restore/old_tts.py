"""
TTS (Text-to-Speech) Cog for Discord Bot
Lightweight, fast TTS using edge-tts (Microsoft neural voices)
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import tempfile
import shutil
from typing import Optional, Dict
from collections import deque
import traceback

# Find ffmpeg executable
FFMPEG_PATH = shutil.which("ffmpeg")

# Windows-specific path detection
if not FFMPEG_PATH and os.name == 'nt':
    import glob
    winget_pattern = os.path.join(
        os.environ.get('LOCALAPPDATA', ''), 
        'Microsoft', 'WinGet', 'Packages', 'Gyan.FFmpeg*', '*', 'bin', 'ffmpeg.exe'
    )
    matches = glob.glob(winget_pattern)
    if matches:
        FFMPEG_PATH = matches[0]

# Try to import edge-tts
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("⚠️ edge-tts not installed. Run: pip install edge-tts")


# Available voices (subset of best ones)
TTS_VOICES = {
    # English US
    "jenny": "en-US-JennyNeural",
    "aria": "en-US-AriaNeural", 
    "guy": "en-US-GuyNeural",
    "davis": "en-US-DavisNeural",
    # English UK
    "sonia": "en-GB-SoniaNeural",
    "ryan": "en-GB-RyanNeural",
    # English Australia
    "natasha": "en-AU-NatashaNeural",
    # Indian English
    "neerja": "en-IN-NeerjaNeural",
    "prabhat": "en-IN-PrabhatNeural",
}


class TTSSession:
    """Manages TTS state for a guild"""
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.voice_client: Optional[discord.VoiceClient] = None
        self.queue: deque = deque()
        self.is_playing = False
        self.current_voice = "en-US-JennyNeural"
        self.temp_dir = os.path.join(tempfile.gettempdir(), f"discord_tts_{guild_id}")
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def cleanup(self):
        """Clean up temp files"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass


class TTS(commands.Cog):
    """Text-to-Speech commands - Type text, bot speaks in voice"""
    
    def __init__(self, bot):
        self.bot = bot
        self.sessions: Dict[int, TTSSession] = {}
    
    def get_session(self, guild_id: int) -> TTSSession:
        """Get or create TTS session for guild"""
        if guild_id not in self.sessions:
            self.sessions[guild_id] = TTSSession(guild_id)
        return self.sessions[guild_id]
    
    async def _generate_tts(self, text: str, voice: str, output_path: str) -> bool:
        """Generate TTS audio file using edge-tts"""
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return True
        except Exception as e:
            print(f"❌ TTS generation error: {e}")
            return False
    
    async def _play_audio(self, session: TTSSession, audio_path: str):
        """Play audio file in voice channel"""
        try:
            if not session.voice_client or not session.voice_client.is_connected():
                return
            
            # Wait for any current audio to finish
            while session.voice_client.is_playing():
                await asyncio.sleep(0.1)
            
            # Create audio source
            if FFMPEG_PATH:
                audio_source = discord.FFmpegPCMAudio(audio_path, executable=FFMPEG_PATH)
            else:
                audio_source = discord.FFmpegPCMAudio(audio_path)
            
            # Play audio
            session.voice_client.play(
                audio_source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._on_audio_complete(session, audio_path, e),
                    self.bot.loop
                )
            )
            
            # Wait for playback to complete
            while session.voice_client and session.voice_client.is_playing():
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"❌ Audio playback error: {e}")
            traceback.print_exc()
    
    async def _on_audio_complete(self, session: TTSSession, audio_path: str, error):
        """Called when audio finishes playing"""
        # Cleanup temp file
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass
        
        # Process next item in queue
        if session.queue:
            await self._process_queue(session)
        else:
            session.is_playing = False
    
    async def _process_queue(self, session: TTSSession):
        """Process the TTS queue"""
        if not session.queue:
            session.is_playing = False
            return
        
        session.is_playing = True
        text, voice = session.queue.popleft()
        
        # Generate unique filename
        audio_path = os.path.join(session.temp_dir, f"tts_{hash(text) % 100000}.mp3")
        
        # Generate TTS
        success = await self._generate_tts(text, voice, audio_path)
        
        if success and os.path.exists(audio_path):
            await self._play_audio(session, audio_path)
        else:
            # Try next in queue
            if session.queue:
                await self._process_queue(session)
            else:
                session.is_playing = False
    
    @app_commands.command(name="tts", description="🔊 Speak text in voice channel using AI voice")
    @app_commands.describe(
        text="The text you want the bot to speak",
        voice="Voice to use (optional: jenny, aria, guy, davis, sonia, ryan, natasha, neerja, prabhat)"
    )
    async def tts(
        self, 
        interaction: discord.Interaction, 
        text: str,
        voice: Optional[str] = None
    ):
        """TTS command - speak text in voice channel"""
        if not EDGE_TTS_AVAILABLE:
            await interaction.response.send_message(
                "❌ TTS is not available. edge-tts library not installed.",
                ephemeral=True
            )
            return
        
        # Check if user is in voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in a voice channel to use TTS!",
                ephemeral=True
            )
            return
        
        # Defer response (TTS generation takes time)
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_channel = interaction.user.voice.channel
            session = self.get_session(interaction.guild_id)
            
            # Resolve voice name
            voice_id = session.current_voice
            if voice:
                voice_lower = voice.lower().strip()
                if voice_lower in TTS_VOICES:
                    voice_id = TTS_VOICES[voice_lower]
                    session.current_voice = voice_id
                else:
                    # Check if it's a full voice ID
                    if "Neural" in voice:
                        voice_id = voice
                        session.current_voice = voice_id
            
            # Connect to voice channel if needed
            if session.voice_client and session.voice_client.is_connected():
                # Move to user's channel if different
                if session.voice_client.channel.id != user_channel.id:
                    await session.voice_client.move_to(user_channel)
            else:
                # Connect to channel
                try:
                    session.voice_client = await user_channel.connect(timeout=10.0)
                except Exception as e:
                    await interaction.followup.send(
                        f"❌ Failed to connect to voice channel: {e}",
                        ephemeral=True
                    )
                    return
            
            # Add to queue
            session.queue.append((text, voice_id))
            
            # Start processing if not already playing
            if not session.is_playing:
                asyncio.create_task(self._process_queue(session))
            
            # Get voice display name
            voice_name = voice_id.replace("Neural", "").split("-")[-1]
            
            await interaction.followup.send(
                f"🔊 Speaking: \"{text[:50]}{'...' if len(text) > 50 else ''}\" (Voice: {voice_name})",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ TTS error: {e}",
                ephemeral=True
            )
            traceback.print_exc()
    
    @app_commands.command(name="tts_voice", description="🎙️ List or set TTS voice")
    @app_commands.describe(voice="Voice name to set (leave empty to see available voices)")
    async def tts_voice(
        self, 
        interaction: discord.Interaction,
        voice: Optional[str] = None
    ):
        """Set or list TTS voices"""
        session = self.get_session(interaction.guild_id)
        
        if not voice:
            # List available voices
            voice_list = "\n".join([f"• **{name}** - {vid}" for name, vid in TTS_VOICES.items()])
            current = session.current_voice.replace("Neural", "").split("-")[-1]
            
            embed = discord.Embed(
                title="🎙️ Available TTS Voices",
                description=f"**Current voice:** {current}\n\n{voice_list}",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Use /tts_voice <name> to change voice")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Set voice
            voice_lower = voice.lower().strip()
            if voice_lower in TTS_VOICES:
                session.current_voice = TTS_VOICES[voice_lower]
                voice_name = session.current_voice.replace("Neural", "").split("-")[-1]
                await interaction.response.send_message(
                    f"✅ TTS voice changed to **{voice_name}**",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Unknown voice: {voice}\nUse `/tts_voice` to see available voices.",
                    ephemeral=True
                )
    
    @app_commands.command(name="tts_stop", description="🛑 Stop TTS playback and clear queue")
    async def tts_stop(self, interaction: discord.Interaction):
        """Stop TTS playback"""
        session = self.get_session(interaction.guild_id)
        
        if session.voice_client and session.voice_client.is_connected():
            # Clear queue
            session.queue.clear()
            session.is_playing = False
            
            # Stop current playback
            if session.voice_client.is_playing():
                session.voice_client.stop()
            
            await interaction.response.send_message("🛑 TTS stopped and queue cleared.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not connected to any voice channel.", ephemeral=True)
    
    @app_commands.command(name="tts_leave", description="👋 Disconnect bot from voice channel")
    async def tts_leave(self, interaction: discord.Interaction):
        """Leave voice channel"""
        session = self.get_session(interaction.guild_id)
        
        if session.voice_client and session.voice_client.is_connected():
            # Clear queue and disconnect
            session.queue.clear()
            session.is_playing = False
            await session.voice_client.disconnect()
            session.voice_client = None
            session.cleanup()
            
            await interaction.response.send_message("👋 Disconnected from voice channel.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not connected to any voice channel.", ephemeral=True)
    
    @commands.Cog.listener()
    async def on_voice_state_update(
        self, 
        member: discord.Member, 
        before: discord.VoiceState, 
        after: discord.VoiceState
    ):
        """Handle voice disconnects - cleanup if bot is alone"""
        if member.id == self.bot.user.id:
            # Bot was disconnected
            if before.channel and not after.channel:
                session = self.sessions.get(member.guild.id)
                if session:
                    session.queue.clear()
                    session.is_playing = False
                    session.voice_client = None
                    session.cleanup()
        else:
            # Check if bot is alone in channel
            session = self.sessions.get(member.guild.id)
            if session and session.voice_client and session.voice_client.is_connected():
                channel = session.voice_client.channel
                # Count non-bot members
                members = [m for m in channel.members if not m.bot]
                if len(members) == 0:
                    # Bot is alone, disconnect after 30 seconds
                    await asyncio.sleep(30)
                    # Re-check if still alone
                    if session.voice_client and session.voice_client.is_connected():
                        members = [m for m in session.voice_client.channel.members if not m.bot]
                        if len(members) == 0:
                            await session.voice_client.disconnect()
                            session.voice_client = None
                            session.cleanup()


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(TTS(bot))
    print("✅ Loaded cogs.tts")
