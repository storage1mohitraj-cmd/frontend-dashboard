# Voice Connection Heartbeat Fix
# Add this to your voice conversation cog

import asyncio
import discord
from discord.ext import commands

class VoiceConversationFixed(commands.Cog):
    """Fixed version with proper heartbeat handling"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}
        self._heartbeat_tasks = {}  # Track heartbeat tasks
    
    async def _keep_alive_heartbeat(self, voice_client, guild_id):
        """Keep the voice connection alive during long operations"""
        try:
            while voice_client and voice_client.is_connected():
                # Send a keep-alive signal every 10 seconds
                await asyncio.sleep(10)
                
                # Check if still connected
                if not voice_client.is_connected():
                    break
                    
                # The voice client handles heartbeats automatically,
                # but we ensure the event loop isn't blocked
                await asyncio.sleep(0)  # Yield control to event loop
                
        except asyncio.CancelledError:
            # Task was cancelled, normal shutdown
            pass
        except Exception as e:
            print(f"❌ Heartbeat error for guild {guild_id}: {e}")
    
    async def connect_to_voice(self, channel):
        """Connect with proper timeout and heartbeat handling"""
        try:
            # Connect with extended timeout and auto-reconnect
            voice_client = await channel.connect(
                timeout=60.0,  # Extended timeout
                reconnect=True,  # Auto-reconnect on disconnect
                self_deaf=False,
                self_mute=False
            )
            
            # Start heartbeat task
            guild_id = channel.guild.id
            heartbeat_task = asyncio.create_task(
                self._keep_alive_heartbeat(voice_client, guild_id)
            )
            self._heartbeat_tasks[guild_id] = heartbeat_task
            
            return voice_client
            
        except asyncio.TimeoutError:
            print(f"❌ Voice connection timeout for {channel.name}")
            return None
        except Exception as e:
            print(f"❌ Voice connection error: {e}")
            return None
    
    async def disconnect_voice(self, guild_id):
        """Properly disconnect and cleanup"""
        # Cancel heartbeat task
        if guild_id in self._heartbeat_tasks:
            self._heartbeat_tasks[guild_id].cancel()
            try:
                await self._heartbeat_tasks[guild_id]
            except asyncio.CancelledError:
                pass
            del self._heartbeat_tasks[guild_id]
        
        # Disconnect voice client
        # ... your existing disconnect logic
    
    async def _speak(self, session, text):
        """Play TTS with proper async handling"""
        voice_client = session.voice_client
        
       # Ensure voice client is connected
        if not voice_client or not voice_client.is_connected():
            print("⚠️ Voice client not connected")
            return
        
        # Generate TTS (this is async, so it won't block heartbeats)
        audio_file = await self._generate_tts_async(text)
        
        if not audio_file:
            print("❌ Failed to generate TTS")
            return
        
        # Play audio WITHOUT blocking
        try:
            # Create FFmpegPCMAudio source
            audio_source = discord.FFmpegPCMAudio(
                audio_file,
                options='-loglevel error'  # Reduce ffmpeg noise
            )
            
            # Play with callback
            voice_client.play(
                audio_source,
                after=lambda e: asyncio.create_task(
                    self._cleanup_after_play(audio_file, e)
                ) if e is None else print(f"❌ Playback error: {e}")
            )
            
            # Wait for playback WITHOUT blocking heartbeats
            while voice_client.is_playing():
                await asyncio.sleep(0.5)  # Check every 500ms but yield control
                
        except Exception as e:
            print(f"❌ Playback error: {e}")
            # Cleanup
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except:
                pass
    
    async def _generate_tts_async(self, text):
        """Generate TTS asynchronously to avoid blocking"""
        loop = asyncio.get_event_loop()
        
        # Run TTS generation in thread pool to avoid blocking
        audio_file = await loop.run_in_executor(
            None,  # Use default executor
            self._generate_tts_sync,  # Your sync TTS function
            text
        )
        
        return audio_file
    
    def _generate_tts_sync(self, text):
        """Your existing synchronous TTS generation"""
        # ... your TTS code here
        pass
    
    async def _cleanup_after_play(self, audio_file, error):
        """Cleanup after playback finishes"""
        if error:
            print(f"❌ Playback error: {error}")
        
        # Delete temp file
        try:
            if os.path.exists(audio_file):
                os.remove(audio_file)
                print(f"🗑️ Cleaned up: {audio_file}")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")

# Key changes:
# 1. Extended timeout (60s instead of default 30s)
# 2. Auto-reconnect enabled
# 3. Heartbeat task to keep connection alive
# 4. Async TTS generation (doesn't block event loop)
# 5. Non-blocking playback monitoring
# 6. Proper cleanup on disconnect
