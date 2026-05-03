"""
Voice Conversation Cog for Discord Bot
Simplified version: Text input → Voice output (TTS only)
Full voice recording requires discord.py[voice] with recording support
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
from typing import Optional, Dict
from datetime import datetime
import traceback

# Import audio processor
try:
    from audio_processor import audio_processor
except ImportError:
    audio_processor = None
    print("⚠️ Could not import audio_processor - voice conversation will not work")

# Import OpenRouter for AI
try:
    from api_manager import make_request
except ImportError:
    make_request = None
    print("⚠️ Could not import AI system - using fallback responses")

# Find ffmpeg executable (Windows-specific path detection)
import shutil
FFMPEG_PATH = shutil.which("ffmpeg")

# If not in PATH, try common Windows locations
if not FFMPEG_PATH and os.name == 'nt':
    import glob
    # Check winget install location
    winget_pattern = os.path.join(
        os.environ.get('LOCALAPPDATA', ''), 
        'Microsoft', 'WinGet', 'Packages', 'Gyan.FFmpeg*', '*', 'bin', 'ffmpeg.exe'
    )
    matches = glob.glob(winget_pattern)
    if matches:
        FFMPEG_PATH = matches[0]
        print(f"✅ Found ffmpeg at: {FFMPEG_PATH}")
    else:
        print("⚠️ ffmpeg not found - voice playback will not work")
        print("   Install with: winget install ffmpeg")



class VoiceSession:
    """Represents an active voice conversation session"""
    
    def __init__(self, guild_id: int, channel_id: int, user_id: int, voice_client: discord.VoiceClient, text_channel: discord.TextChannel):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.user_id = user_id
        self.voice_client = voice_client
        self.text_channel = text_channel
        self.conversation_history = []
        self.is_speaking = False
        self.start_time = datetime.now()
        self.message_count = 0
        
    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now()
        })
        self.message_count += 1
    
    def get_context(self, max_messages: int = 10) -> list:
        """Get recent conversation context for AI"""
        recent = self.conversation_history[-max_messages:]
        return [{"role": msg["role"], "content": msg["content"]} for msg in recent]


class VoiceConversation(commands.Cog):
    """Voice conversation commands - Text to Voice"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions: Dict[int, VoiceSession] = {}
        print("🎙️ Voice Conversation cog loaded (Text→Voice mode)")
    
    @app_commands.command(name="voice_chat", description="Start voice conversation (type messages, bot responds with voice)")
    async def voice_chat(self, interaction: discord.Interaction):
        """Start voice conversation - you type, bot speaks"""
        try:
            # Check if user is in a voice channel
            if not interaction.user.voice:
                await interaction.response.send_message(
                    "❌ You need to be in a voice channel!\n"
                    "Join a voice channel first, then try again.",
                    ephemeral=True
                )
                return
            
            # Check if already active
            if interaction.guild.id in self.active_sessions:
                await interaction.response.send_message(
                    "❌ Voice conversation already active!\n"
                    f"Use `/end_voice_chat` to end it first.",
                    ephemeral=True
                )
                return
            
            voice_channel = interaction.user.voice.channel
            await interaction.response.defer()
            
            try:
                # Connect to voice
                voice_client = await voice_channel.connect(timeout=30.0, self_deaf=True)
                
                # Create session
                session = VoiceSession(
                    guild_id=interaction.guild.id,
                    channel_id=voice_channel.id,
                    user_id=interaction.user.id,
                    voice_client=voice_client,
                    text_channel=interaction.channel
                )
                self.active_sessions[interaction.guild.id] = session
                
                # Set voice channel status
                try:
                    await voice_channel.edit(status="🤖 AI voice assistant: Molly")
                except Exception as e:
                    print(f"⚠️ Could not set voice channel status: {e}")
                
                # Welcome message
                embed = discord.Embed(
                    title="🎙️ Voice Chat Active!",
                    description=(
                        f"**Connected to:** {voice_channel.mention}\n\n"
                        "**How it works:**\n"
                        "• Type your messages in this channel\n"
                        "• I'll respond with **voice** in the voice channel\n"
                        "• Say 'goodbye' in text or use `/end_voice_chat` to stop\n\n"
                        "**Note:** This is text→voice mode. For full voice conversation,\n"
                        "discord.py voice recording support is needed.\n"
                    ),
                    color=0x00FF00
                )
                embed.set_footer(text=f"Started by {interaction.user.name}")
                
                await interaction.followup.send(embed=embed)
                
                # Speak greeting
                await self._speak(session, "Hello! I'm listening. Type your messages and I'll respond with voice!")
                
            except discord.ClientException:
                await interaction.followup.send(
                    "❌ Already connected to voice!",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Connection failed: {e}",
                    ephemeral=True
                )
                traceback.print_exc()
                
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
            except:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            traceback.print_exc()
    
    @app_commands.command(name="end_voice_chat", description="End voice conversation")
    async def end_voice_chat(self, interaction: discord.Interaction):
        """End voice conversation"""
        try:
            if interaction.guild.id not in self.active_sessions:
                await interaction.response.send_message(
                    "❌ No active voice conversation!",
                    ephemeral=True
                )
                return
            
            session = self.active_sessions[interaction.guild.id]
            await interaction.response.defer()
            
            # Goodbye
            await self._speak(session, "Goodbye! It was nice talking. See you next time!")
            await asyncio.sleep(3)
            
            # Cleanup
            await self._cleanup_session(interaction.guild.id)
            
            # Summary
            duration = (datetime.now() - session.start_time).total_seconds()
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            
            embed = discord.Embed(
                title="👋 Voice Chat Ended",
                description=(
                    f"**Duration:** {minutes}m {seconds}s\n"
                    f"**Messages:** {session.message_count}\n\n"
                    "Use `/voice_chat` to start again!"
                ),
                color=0xFF5555
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
            traceback.print_exc()
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages in active voice chat sessions"""
        try:
            # Ignore bots
            if message.author.bot:
                return
            
            # Check if this guild has an active session
            if message.guild.id not in self.active_sessions:
                return
            
            session = self.active_sessions[message.guild.id]
            
            # Only process messages from the text channel where session started
            if message.channel.id != session.text_channel.id:
                return
            
            # Get message content
            user_text = message.content.strip()
            if not user_text:
                return
            
            print(f"📝 Processing message: {user_text}")
            
            # Add to history
            session.add_message("user", user_text)
            
            # Check for goodbye
            if any(word in user_text.lower() for word in ["goodbye", "bye", "see you", "end chat"]):
                await message.channel.send(f"👋 {message.author.mention} said goodbye!")
                await self._cleanup_session(message.guild.id)
                return
            
            # Get AI response
            ai_response = await self._get_ai_response(session, user_text)
            
            if not ai_response:
                ai_response = "I didn't quite understand that. Could you rephrase?"
            
            print(f"🤖 AI Response: {ai_response}")
            
            # Add to history
            session.add_message("assistant", ai_response)
            
            # Show typing indicator
            async with message.channel.typing():
                # Speak response
                await self._speak(session, ai_response)
            
            # Also send as text for reference
            await message.reply(f"🔊 *Speaking:* {ai_response}", mention_author=False)
            
        except Exception as e:
            print(f"❌ Error in on_message: {e}")
            traceback.print_exc()
    
    async def _get_ai_response(self, session: VoiceSession, user_text: str) -> str:
        """Get AI response"""
        try:
            if make_request:
                system_prompt = (
                    "You are Molly, a friendly Discord bot in a voice conversation. "
                    "Keep responses SHORT (1-2 sentences) since they'll be spoken aloud. "
                    "Be natural and conversational."
                )
                
                context = session.get_context(max_messages=6)
                messages = [{"role": "system", "content": system_prompt}] + context
                
                response = await make_request(messages=messages)
                
                if response and response.strip():
                    response = response.strip()
                    # Limit length
                    if len(response) > 200:
                        sentences = response.split('. ')
                        response = sentences[0] + '.'
                    return response
                else:
                    return "I didn't get that. Can you say it differently?"
            else:
                # Fallback
                import random
                return random.choice([
                    "That's interesting! Tell me more.",
                    "I see. What else?",
                    "That's a great point!",
                ])
                
        except Exception as e:
            print(f"❌ Error getting AI response: {e}")
            return "I had trouble with that. Try again?"
    
    async def _speak(self, session: VoiceSession, text: str):
        """Convert text to speech and play"""
        try:
            session.is_speaking = True
            
            if not audio_processor:
                print("❌ Audio processor not available")
                session.is_speaking = False
                return
            
            # Generate TTS
            audio_bytes = await audio_processor.text_to_speech(text, language="en")
            
            if not audio_bytes:
                print("❌ TTS failed")
                session.is_speaking = False
                return
            
            # Save temp
            temp_path = await audio_processor.save_temp_audio(audio_bytes, format="mp3")
            
            if not temp_path:
                print("❌ Save failed")
                session.is_speaking = False
                return
            
            # Play audio using FFmpeg
            if FFMPEG_PATH:
                audio_source = discord.FFmpegPCMAudio(temp_path, executable=FFMPEG_PATH)
            else:
                audio_source = discord.FFmpegPCMAudio(temp_path)
            
            # Play and wait for finish
            if session.voice_client and session.voice_client.is_connected():
                # Wait for any current audio to finish first
                max_wait = 30  # Maximum 30 seconds wait
                wait_count = 0
                while session.voice_client.is_playing() and wait_count < max_wait * 10:
                    await asyncio.sleep(0.1)
                    wait_count += 1
                
                # Now play the new audio
                session.voice_client.play(
                    audio_source,
                    after=lambda e: print(f"✅ Done speaking") if not e else print(f"❌ Play error: {e}")
                )
                
                # Wait for this audio to finish
                while session.voice_client.is_playing():
                    await asyncio.sleep(0.1)
            
            # Cleanup
            try:
                os.remove(temp_path)
            except:
                pass
            
            session.is_speaking = False
            
        except Exception as e:
            print(f"❌ Error speaking: {e}")
            traceback.print_exc()
            session.is_speaking = False
    
    async def _cleanup_session(self, guild_id: int):
        """Cleanup session"""
        try:
            if guild_id in self.active_sessions:
                session = self.active_sessions[guild_id]
                
                # Clear voice channel status
                if session.voice_client and session.voice_client.channel:
                    try:
                        await session.voice_client.channel.edit(status=None)
                    except Exception as e:
                        print(f"⚠️ Could not clear voice channel status: {e}")
                
                if session.voice_client and session.voice_client.is_connected():
                    await session.voice_client.disconnect(force=True)
                
                del self.active_sessions[guild_id]
                print(f"✅ Cleaned up session for guild {guild_id}")
                
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice disconnects"""
        try:
            if member.guild.id not in self.active_sessions:
                return
            
            session = self.active_sessions[member.guild.id]
            
            # Bot disconnected
            if member == member.guild.me and after.channel is None:
                await self._cleanup_session(member.guild.id)
                print("🛑 Bot disconnected - cleaned up")
            
            # User left
            elif member.id == session.user_id and after.channel is None:
                await asyncio.sleep(30)
                member_updated = member.guild.get_member(member.id)
                if not member_updated.voice or member_updated.voice.channel.id != session.channel_id:
                    await self._cleanup_session(member.guild.id)
                    print("🛑 User left - cleaned up")
                    
        except Exception as e:
            print(f"⚠️ Voice state error: {e}")


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(VoiceConversation(bot))
