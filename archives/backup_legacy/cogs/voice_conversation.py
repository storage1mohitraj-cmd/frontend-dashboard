"""
Voice Conversation Cog - FIXED VERSION with Heartbeat Timeout Fix
Handles voice chat sessions with proper async handling to prevent disconnections
"""

import discord
from discord.ext import commands
import asyncio
import os
import tempfile
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Try to import TTS library
try:
    from gtts import gTTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logger.warning("⚠️ gTTS not available - TTS features disabled")

# Try to import AI system
try:
    from api_manager import make_request
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logger.warning("⚠️ AI system not available - using fallback responses")


class VoiceSession:
    """Represents an active voice conversation session"""

    def __init__(self, guild_id: int, channel_id: int, user_id: int, voice_client: discord.VoiceClient, text_channel: discord.TextChannel):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.user_id = user_id
        self.voice_client = voice_client
        self.text_channel = text_channel
        self.conversation_history = []
        self.created_at = datetime.utcnow()

    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow()
        })

    def get_context(self, max_messages: int = 10):
        """Get recent conversation context for AI"""
        recent = self.conversation_history[-max_messages:]
        return [{"role": msg["role"], "content": msg["content"]} for msg in recent]


class EndCallView(discord.ui.View):
    """View with End Call button for voice conversation"""

    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="🔴 End Call", style=discord.ButtonStyle.danger, custom_id="end_voice_call")
    async def end_call_button(self, interaction: discord.ApplicationContext, button: discord.ui.Button):
        """Handle End Call button press"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Check if user has permission
            if self.guild_id not in self.cog.active_sessions:
                await interaction.followup.send("❌ No active voice session found.", ephemeral=True)
                return

            session = self.cog.active_sessions[self.guild_id]

            # Only the user who started the session or admins can end it
            if interaction.user.id != session.user_id and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ Only the user who started the session or administrators can end it.", ephemeral=True)
                return

            # End the session
            await self.cog._cleanup_session(self.guild_id)

            await interaction.followup.send("✅ Voice chat session ended.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error ending voice session: {e}")
            await interaction.followup.send("❌ Error ending session.", ephemeral=True)


class VoiceConversation(commands.Cog):
    """Voice conversation commands - Text to Voice with Heartbeat Fix"""

    def __init__(self, bot):
        self.bot = bot
        self.active_sessions: Dict[int, VoiceSession] = {}
        self._temp_dir = tempfile.mkdtemp(prefix="discord_voice_chat_")
        logger.info(f"📁 Voice temp directory: {self._temp_dir}")

    @discord.slash_command(name="voice_chat", description="Start AI voice conversation")
    async def voice_chat(self, interaction: discord.ApplicationContext):
        """Start voice conversation - you type, bot speaks"""

        # Check if user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in a voice channel to start a voice chat!",
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id

        # Check if session already exists
        if guild_id in self.active_sessions:
            await interaction.response.send_message(
                "⚠️ A voice chat session is already active in this server!",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Connect to voice channel with EXTENDED TIMEOUT and AUTO-RECONNECT
            voice_channel = interaction.user.voice.channel

            # Try connecting with retry logic
            voice_client = None
            for attempt in range(3):
                try:
                    voice_client = await voice_channel.connect(
                        timeout=60.0,        # Extended timeout (was 30s default)
                        reconnect=True,       # Auto-reconnect on disconnect
                        self_deaf=False,
                        self_mute=False
                    )
                    break  # Success
                except asyncio.TimeoutError:
                    logger.warning(f"Voice connection attempt {attempt + 1}/3 timed out")
                    if attempt < 2:
                        await asyncio.sleep(2)
                    else:
                        raise

            if not voice_client:
                await interaction.followup.send(
                    "❌ Failed to connect to voice channel after 3 attempts.",
                    ephemeral=True
                )
                return

            # Create session
            session = VoiceSession(
                guild_id=guild_id,
                channel_id=voice_channel.id,
                user_id=interaction.user.id,
                voice_client=voice_client,
                text_channel=interaction.channel
            )

            self.active_sessions[guild_id] = session

            # Set voice channel status
            try:
                await voice_channel.edit(status="🎙️ AI Voice Assistant: Molly")
            except:
                pass  # Status update is optional

            # Send control message with End Call button
            view = EndCallView(self, guild_id)
            await interaction.followup.send(
                "✅ **Voice Chat Started!**\n"
                f"🎙️ Connected to **{voice_channel.name}**\n\n"
                "**How to use:**\n"
                "• Type messages in this channel\n"
                "• I'll respond with voice in the voice channel\n"
                "• Click the button below to end the session\n\n"
                "**System:** Heartbeat timeout fix enabled ✅",
                view=view,
                ephemeral=True
            )

            # Welcome message
            welcome_text = "Hello! I'm Molly, your AI voice assistant. How can I help you today?"
            await self._speak(session, welcome_text)
            session.add_message("assistant", welcome_text)

        except discord.ClientException as e:
            await interaction.followup.send(
                f"❌ Voice connection error: {str(e)}\n"
                "The bot might already be in another voice channel.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error starting voice chat: {e}")
            await interaction.followup.send(
                f"❌ Error starting voice chat: {str(e)}",
                ephemeral=True
            )
            # Cleanup on error
            if guild_id in self.active_sessions:
                await self._cleanup_session(guild_id)

    @discord.slash_command(name="end_voice_chat", description="End voice conversation")
    async def end_voice_chat(self, interaction: discord.ApplicationContext):
        """End voice conversation"""
        guild_id = interaction.guild.id

        if guild_id not in self.active_sessions:
            await interaction.response.send_message(
                "❌ No active voice chat session in this server.",
                ephemeral=True
            )
            return

        session = self.active_sessions[guild_id]

        # Check permissions
        if interaction.user.id != session.user_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only the user who started the session or administrators can end it.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        await self._cleanup_session(guild_id)

        await interaction.followup.send(
            "✅ Voice chat session ended.",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages in active voice chat sessions - OPTIMIZED for speed"""

        # Ignore bot messages
        if message.author.bot:
            return

        guild_id = message.guild.id if message.guild else None

        # Check if there's an active session in this guild
        if guild_id not in self.active_sessions:
            return

        session = self.active_sessions[guild_id]

        # Only respond to messages in the session's text channel
        if message.channel.id != session.text_channel.id:
            return

        # Get user message
        user_text = message.content.strip()
        if not user_text:
            return

        logger.info(f"📝 Processing message: {user_text}")

        # IMMEDIATE FEEDBACK: Start typing indicator
        async with message.channel.typing():
            # Add to conversation history
            session.add_message("user", user_text)

            # Quick reaction to show we're processing
            try:
                await message.add_reaction("🎙️")
            except:
                pass

            # Get AI response (optimized for speed)
            ai_response = await self._get_ai_response(session, user_text)

            # Add to history
            session.add_message("assistant", ai_response)

            logger.info(f"🤖 AI Response: {ai_response}")

        # Remove reaction and add done reaction
        try:
            await message.remove_reaction("🎙️", self.bot.user)
            await message.add_reaction("✅")
        except:
            pass

        # Speak the response (this happens after text feedback)
        await self._speak(session, ai_response)

    async def _get_ai_response(self, session: VoiceSession, user_text: str) -> str:
        """Get AI response - ASYNC to avoid blocking heartbeats"""

        if not AI_AVAILABLE:
            # Fallback response
            return "I'm sorry, I'm currently operating in limited mode. My AI capabilities are temporarily unavailable."

        try:
            # Build context (REDUCED for speed)
            messages = session.get_context(max_messages=5)

            # System prompt (optimized for brevity)
            system_prompt = "You are Molly, a friendly AI voice assistant. Give SHORT, conversational responses (1-2 sentences max) since they'll be spoken aloud."

            # Make AI request - this is already async, yields control
            response = await make_request(
                messages=messages,
                system_prompt=system_prompt,
                user_id=session.user_id,
                max_tokens=80  # REDUCED for faster responses
            )

            # Yield control to event loop
            await asyncio.sleep(0)

            return response.strip() if response else "I'm not sure how to respond to that."

        except Exception as e:
            logger.error(f"AI request error: {e}")
            return "I'm having trouble processing that request right now."

    async def _speak(self, session: VoiceSession, text: str):
        """Convert text to speech and play - FIXED VERSION with async handling"""

        voice_client = session.voice_client

        # Safety check - ensure connected
        if not voice_client or not voice_client.is_connected():
            logger.warning("⚠️ Voice client not connected, skipping playback")
            return

        if not TTS_AVAILABLE:
            logger.warning("⚠️ TTS not available")
            return

        try:
            # Generate TTS file ASYNCHRONOUSLY (doesn't block event loop!)
            loop = asyncio.get_event_loop()
            audio_path = await loop.run_in_executor(
                None,  # Use default thread pool
                self._generate_tts_sync,
                text,
                session.guild_id
            )

            if not audio_path or not os.path.exists(audio_path):
                logger.error("❌ TTS generation failed")
                return

            # Wait if already playing
            if voice_client.is_playing():
                voice_client.stop()
                await asyncio.sleep(0.1)

            # Create audio source
            audio_source = discord.FFmpegPCMAudio(
                audio_path,
                options='-loglevel error'  # Reduce ffmpeg output
            )

            # Setup cleanup callback
            def cleanup(error):
                if error:
                    logger.error(f"❌ Playback error: {error}")
                # Schedule async cleanup
                asyncio.create_task(self._cleanup_audio_file(audio_path))

            # Play audio
            voice_client.play(audio_source, after=cleanup)

            # Wait for playback WITHOUT blocking event loop
            while voice_client.is_playing():
                await asyncio.sleep(0.5)  # Check every 500ms, yields control

                # Safety check
                if not voice_client.is_connected():
                    logger.warning("⚠️ Voice client disconnected during playback")
                    break

            logger.info("✅ Done speaking")

        except Exception as e:
            logger.error(f"TTS error: {e}")
            # Cleanup on error
            if 'audio_path' in locals() and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except:
                    pass

    def _generate_tts_sync(self, text: str, guild_id: int) -> Optional[str]:
        """Generate TTS file synchronously (runs in thread pool)"""
        try:
            # Create unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"voice_response_{guild_id}_{timestamp}.mp3"
            filepath = os.path.join(self._temp_dir, filename)

            # Generate TTS
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(filepath)

            return filepath

        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            return None

    async def _cleanup_audio_file(self, filepath: str):
        """Cleanup audio file after playback"""
        try:
            if os.path.exists(filepath):
                # Small delay to ensure playback finished
                await asyncio.sleep(0.5)
                os.remove(filepath)
                logger.info(f"🗑️ Cleaned up: {filepath}")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup failed for {filepath}: {e}")

    async def _cleanup_session(self, guild_id: int):
        """Cleanup session"""
        if guild_id not in self.active_sessions:
            return

        session = self.active_sessions[guild_id]

        try:
            # Clear voice channel status
            try:
                channel = self.bot.get_channel(session.channel_id)
                if channel and hasattr(channel, 'edit'):
                    await channel.edit(status=None)
                    logger.info("✅ Voice channel status cleared")
            except:
                pass

            # Disconnect from voice
            if session.voice_client and session.voice_client.is_connected():
                await session.voice_client.disconnect(force=True)

            # Remove session
            del self.active_sessions[guild_id]

            logger.info(f"✅ Cleaned up session for guild {guild_id}")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice disconnects"""

        # Check if bot was disconnected
        if member.id != self.bot.user.id:
            return

        # Bot left a voice channel
        if before.channel and not after.channel:
            guild_id = before.channel.guild.id
            if guild_id in self.active_sessions:
                logger.info("🛑 Bot disconnected - cleaned up")
                await self._cleanup_session(guild_id)

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        # Cleanup all sessions
        for guild_id in list(self.active_sessions.keys()):
            try:
                asyncio.create_task(self._cleanup_session(guild_id))
            except:
                pass


def setup(bot):
    """Load the cog"""
    bot.add_cog(VoiceConversation(bot))
