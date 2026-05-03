import discord
from discord.ext import commands, tasks
import json
import logging
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Optional
import os
import calendar
import asyncio

try:
    from db.mongo_adapters import mongo_enabled, BirthdaysAdapter, BirthdayChannelAdapter
except Exception:
    mongo_enabled = lambda: False
    BirthdaysAdapter = None
    BirthdayChannelAdapter = None

logger = logging.getLogger(__name__)

BIRTHDAYS_FILE = Path(__file__).parent.parent / "birthdays.json"
SENT_WISHES_FILE = Path(__file__).parent.parent / "sent_wishes.json"


def to_superscript(text: str) -> str:
    """Convert text to superscript Unicode characters"""
    superscript_map = {
        'A': 'ᴬ', 'B': 'ᴮ', 'C': 'ᶜ', 'D': 'ᴰ', 'E': 'ᴱ', 'F': 'ᶠ', 'G': 'ᴳ', 'H': 'ᴴ',
        'I': 'ᴵ', 'J': 'ᴶ', 'K': 'ᴷ', 'L': 'ᴸ', 'M': 'ᴹ', 'N': 'ᴺ', 'O': 'ᴼ', 'P': 'ᴾ',
        'Q': 'Q', 'R': 'ᴿ', 'S': 'ˢ', 'T': 'ᵀ', 'U': 'ᵁ', 'V': 'ⱽ', 'W': 'ᵂ', 'X': 'ˣ',
        'Y': 'ʸ', 'Z': 'ᶻ',
        'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ',
        'i': 'ⁱ', 'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ', 'p': 'ᵖ',
        'q': 'q', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ', 'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ',
        'y': 'ʸ', 'z': 'ᶻ'
    }
    return ''.join(superscript_map.get(char, char) for char in text)


class BirthdayWishView(discord.ui.View):
    """Persistent view for birthday wish button"""
    def __init__(self, birthday_user_ids: list):
        super().__init__(timeout=None)
        # Store birthday user IDs as a comma-separated string for the custom_id
        self.birthday_user_ids = birthday_user_ids
        # Create custom_id with user IDs (limited to 100 chars)
        user_ids_str = ",".join(str(uid) for uid in birthday_user_ids[:10])  # Limit to 10 users
        self.wish_button.custom_id = f"birthday_wish_{user_ids_str}"
        self.gift_button.custom_id = f"birthday_gift_{user_ids_str}"
        self.annoy_button.custom_id = f"birthday_annoy_{user_ids_str}"
        self.gif_button.custom_id = f"birthday_gif_{user_ids_str}"
        self.dice_button.custom_id = f"birthday_dice_{user_ids_str}"
    
    @discord.ui.button(label="🎉 Wish Happy Birthday", style=discord.ButtonStyle.primary)
    async def wish_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Extract user IDs from custom_id
            user_ids_str = button.custom_id.replace("birthday_wish_", "")
            birthday_user_ids = [int(uid) for uid in user_ids_str.split(",")]
            
            # Check if the person clicking is one of the birthday users
            if interaction.user.id in birthday_user_ids:
                await interaction.response.send_message(
                    "🎂 You can't wish yourself a happy birthday! Let others celebrate you! 😊",
                    ephemeral=True
                )
                return
            
            # Fetch birthday users
            birthday_users = []
            for user_id in birthday_user_ids:
                try:
                    user = await interaction.client.fetch_user(user_id)
                    if user:
                        birthday_users.append(user)
                except Exception:
                    pass
            
            if not birthday_users:
                await interaction.response.send_message(
                    "❌ Could not find the birthday user(s).",
                    ephemeral=True
                )
                return
            
            # Create personalized wish message
            birthday_mentions = [user.mention for user in birthday_users]
            wish_message = (
                f"🎉 **Happy Birthday** {', '.join(birthday_mentions)}! 🎂\n\n"
                f"— From {interaction.user.mention} 💝"
            )
            
            # Send the wish in the channel
            await interaction.response.send_message(wish_message)
            
            logger.info(f"🎉 {interaction.user.id} sent birthday wish to {birthday_user_ids}")
            
        except Exception as e:
            logger.error(f"❌ Error in birthday wish button: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Failed to send birthday wish. Please try again!",
                    ephemeral=True
                )
            except:
                pass
    
    @discord.ui.button(label="🎁", style=discord.ButtonStyle.success)
    async def gift_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Extract user IDs from custom_id
            user_ids_str = button.custom_id.replace("birthday_gift_", "")
            birthday_user_ids = [int(uid) for uid in user_ids_str.split(",")]
            
            # Check if the person clicking is one of the birthday users
            if interaction.user.id in birthday_user_ids:
                # Birthday person trying to send themselves a gift - show humorous message
                embed = discord.Embed(
                    title="🎂 Nice Try!",
                    description=(
                        "You can't send yourself a birthday gift! 😂\n\n"
                        "That's like trying to surprise yourself with your own party!\n\n"
                        "Sit back, relax, and let others celebrate you today! 🎉"
                    ),
                    color=0xFF69B4  # Hot pink
                )
                embed.set_footer(text="Enjoy your special day! 🎈")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Fetch birthday users for the message
            birthday_users = []
            for user_id in birthday_user_ids:
                try:
                    user = await interaction.client.fetch_user(user_id)
                    if user:
                        birthday_users.append(user)
                except Exception:
                    pass
            
            if not birthday_users:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Could not find the birthday user(s).",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Create the gift message with birthday user mentions
            birthday_names = [user.display_name for user in birthday_users]
            birthday_name_str = ", ".join(birthday_names)
            
            # Convert birthday name to superscript for the name change suggestion
            birthday_name_super = to_superscript(birthday_name_str)
            
            # Get the user who clicked the button
            clicker_name = interaction.user.display_name
            
            # Create professional embed with gift ideas
            embed = discord.Embed(
                title="🎁 Gift Ideas",
                description=f"Here are some fun ways to celebrate **{birthday_name_str}**'s birthday:",
                color=0x00FF00  # Green
            )
            
            embed.add_field(
                name="🏰 Resource Share",
                value=f"Plunder your resources and Let **{birthday_name_str}** attack you once !",
                inline=False
            )
            
            embed.add_field(
                name="⭐ Share Froststars",
                value="(Official Link)[https://store.centurygames.com/wos",
                inline=False
            )
        
            
            embed.add_field(
                name="✨ Name Change",
                value=f"Change your name to **{clicker_name} ᴴᴮᴰ {birthday_name_super}**",
                inline=False
            )
            embed.add_field(
                name="Music 🎵 ",
                value=f"✨ You can play a music for **{birthday_name_str}**",
                inline=False
            )
            
            embed.set_footer(text="or just try to make their day special in your own way! 🎉")
            
            # Send ephemeral message (only visible to the user who clicked)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"🎁 {interaction.user.id} clicked gift button for {birthday_user_ids}")
            
        except Exception as e:
            logger.error(f"❌ Error in birthday gift button: {e}")
            try:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Failed to process gift. Please try again!",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                pass
    
    @discord.ui.button(label="🚨", style=discord.ButtonStyle.danger)
    async def annoy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Extract user IDs from custom_id
            user_ids_str = button.custom_id.replace("birthday_annoy_", "")
            birthday_user_ids = [int(uid) for uid in user_ids_str.split(",")]
            
            # Check if the person clicking is one of the birthday users
            if interaction.user.id in birthday_user_ids:
                await interaction.response.send_message(
                    "😂 You can't annoy yourself! That's just... sad. Let others do it for you! 🎉",
                    ephemeral=True
                )
                return
            
            # Fetch birthday users
            birthday_users = []
            for user_id in birthday_user_ids:
                try:
                    user = await interaction.client.fetch_user(user_id)
                    if user:
                        birthday_users.append(user)
                except Exception:
                    pass
            
            if not birthday_users:
                await interaction.response.send_message(
                    "❌ Could not find the birthday user(s).",
                    ephemeral=True
                )
                return
            
            # Create spam message by tagging the user multiple times (no text, just tags)
            birthday_mentions = [user.mention for user in birthday_users]
            spam_parts = []
            
            # Tag the user 10 times with just their mention
            for _ in range(10):
                spam_parts.append(' '.join(birthday_mentions))
            
            spam_message = "\n".join(spam_parts)
            
            # Send the annoy spam
            await interaction.response.send_message(spam_message)
            
            logger.info(f"😈 {interaction.user.id} annoyed birthday user(s) {birthday_user_ids}")
            
        except Exception as e:
            logger.error(f"❌ Error in birthday annoy button: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Failed to annoy. Maybe that's a good thing! 😅",
                    ephemeral=True
                )
            except:
                pass
    
    @discord.ui.button(label="🥳🎂", style=discord.ButtonStyle.secondary)
    async def gif_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Extract user IDs from custom_id
            user_ids_str = button.custom_id.replace("birthday_gif_", "")
            birthday_user_ids = [int(uid) for uid in user_ids_str.split(",")]
            
            # Check if the person clicking is one of the birthday users
            if interaction.user.id in birthday_user_ids:
                await interaction.response.send_message(
                    "🎉 You can't send yourself a birthday GIF! Let others celebrate you! 🎂",
                    ephemeral=True
                )
                return
            
            # Fetch birthday users
            birthday_users = []
            for user_id in birthday_user_ids:
                try:
                    user = await interaction.client.fetch_user(user_id)
                    if user:
                        birthday_users.append(user)
                except Exception:
                    pass
            
            if not birthday_users:
                await interaction.response.send_message(
                    "❌ Could not find the birthday user(s).",
                    ephemeral=True
                )
                return
            
            # Defer response as we're fetching from API
            if not interaction.response.is_done():
                await interaction.response.defer()
            
            # Fetch random birthday GIF from Tenor
            import aiohttp
            import random
            
            # Tenor API key (you can get a free one from https://tenor.com/developer/keyregistration)
            # For now, we'll use a public endpoint that doesn't require auth
            tenor_api_key = os.getenv('TENOR_API_KEY', 'AIzaSyAyimkuYQYF_FXVALexPuGQctUWRURdCYQ')  # Default test key
            
            search_terms = [
                "happy birthday",
                "birthday celebration",
                "birthday party",
                "birthday cake",
                "birthday dance",
                "birthday confetti"
            ]
            
            search_term = random.choice(search_terms)
            
            try:
                async with aiohttp.ClientSession() as session:
                    # Tenor API v2 endpoint
                    url = f"https://tenor.googleapis.com/v2/search?q={search_term}&key={tenor_api_key}&client_key=discord_bot&limit=50"
                    
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get('results', [])
                            
                            if results:
                                # Pick a random GIF from results
                                gif = random.choice(results)
                                gif_url = gif['media_formats']['gif']['url']
                                
                                # Create embed with GIF
                                birthday_mentions = [user.mention for user in birthday_users]
                                embed = discord.Embed(
                                    description=f"🎉 {', '.join(birthday_mentions)} 🎂\n\n— From {interaction.user.mention} 🎁",
                                    color=0xFF69B4
                                )
                                embed.set_image(url=gif_url)
                                
                                await interaction.followup.send(embed=embed)
                                logger.info(f"🎁 {interaction.user.id} sent birthday GIF to {birthday_user_ids}")
                            else:
                                # Fallback GIF if no results
                                birthday_mentions = [user.mention for user in birthday_users]
                                fallback_gifs = [
                                    "https://media.tenor.com/kHcmsxlKHEAAAAAC/happy-birthday.gif",
                                    "https://media.tenor.com/x2BVlJjHLbgAAAAC/happy-birthday-birthday.gif",
                                    "https://media.tenor.com/OKSJcAzRi8QAAAAC/happy-birthday.gif",
                                    "https://media.tenor.com/3EdZNdU9DYEAAAAC/happy-birthday-cake.gif"
                                ]
                                gif_url = random.choice(fallback_gifs)
                                embed = discord.Embed(
                                    description=f"🎉 {', '.join(birthday_mentions)} 🎂\n\n— From {interaction.user.mention} 🎁",
                                    color=0xFF69B4
                                )
                                embed.set_image(url=gif_url)
                                await interaction.followup.send(embed=embed)
                        else:
                            # API error, use fallback
                            birthday_mentions = [user.mention for user in birthday_users]
                            fallback_gifs = [
                                "https://media.tenor.com/kHcmsxlKHEAAAAAC/happy-birthday.gif",
                                "https://media.tenor.com/x2BVlJjHLbgAAAAC/happy-birthday-birthday.gif",
                                "https://media.tenor.com/OKSJcAzRi8QAAAAC/happy-birthday.gif",
                                "https://media.tenor.com/3EdZNdU9DYEAAAAC/happy-birthday-cake.gif"
                            ]
                            gif_url = random.choice(fallback_gifs)
                            embed = discord.Embed(
                                description=f"🎉 {', '.join(birthday_mentions)} 🎂\n\n— From {interaction.user.mention} 🎁",
                                color=0xFF69B4
                            )
                            embed.set_image(url=gif_url)
                            await interaction.followup.send(embed)
            except Exception as e:
                logger.error(f"Failed to fetch GIF from Tenor: {e}")
                # Use fallback GIFs
                birthday_mentions = [user.mention for user in birthday_users]
                fallback_gifs = [
                    "https://media.tenor.com/kHcmsxlKHEAAAAAC/happy-birthday.gif",
                    "https://media.tenor.com/x2BVlJjHLbgAAAAC/happy-birthday-birthday.gif",
                    "https://media.tenor.com/OKSJcAzRi8QAAAAC/happy-birthday.gif",
                    "https://media.tenor.com/3EdZNdU9DYEAAAAC/happy-birthday-cake.gif"
                ]
                gif_url = random.choice(fallback_gifs)
                embed = discord.Embed(
                    description=f"🎉 {', '.join(birthday_mentions)} 🎂\n\n— From {interaction.user.mention} 🎁",
                    color=0xFF69B4
                )
                embed.set_image(url=gif_url)
                await interaction.followup.send(embed)
            
        except Exception as e:
            logger.error(f"❌ Error in birthday GIF button: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ Failed to send birthday GIF. Please try again!",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ Failed to send birthday GIF. Please try again!",
                        ephemeral=True
                    )
            except:
                pass
    
    @discord.ui.button(label="🎲", style=discord.ButtonStyle.secondary)
    async def dice_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            import random
            import asyncio
            
            # Dice assets
            DICE_GIF_URL = "https://cdn.discordapp.com/attachments/1435569370389807144/1435585171658379385/ezgif-6882c768e3ab08.gif"
            DICE_FACE_URLS = {
                1: "https://cdn.discordapp.com/attachments/1435569370389807144/1435586859098181632/Screenshot_20251105-153253copyad.png",
                2: "https://cdn.discordapp.com/attachments/1435569370389807144/1435587042154385510/2idce_2.png",
                3: "https://cdn.discordapp.com/attachments/1435569370389807144/1435589652353388565/3dice_1.png",
                4: "https://cdn.discordapp.com/attachments/1435569370389807144/1435585681987735582/Screenshot_20251105-153253copy.png",
                5: "https://cdn.discordapp.com/attachments/1435569370389807144/1435587924036026408/5dice_1.png",
                6: "https://cdn.discordapp.com/attachments/1435569370389807144/1435589024147570708/6dice_1.png",
            }
            
            # Defer and show rolling animation
            await interaction.response.defer()
            
            # Send rolling GIF
            rolling_embed = discord.Embed(
                title=f"{interaction.user.display_name} rolls the dice...",
                color=0x2ecc71
            )
            rolling_embed.set_image(url=DICE_GIF_URL)
            rolling_msg = await interaction.followup.send(embed=rolling_embed)
            
            # Wait for animation
            await asyncio.sleep(2.0)
            
            # Roll the dice
            result = random.randint(1, 6)
            result_embed = discord.Embed(
                title=f"🎲 {interaction.user.display_name} rolled a {result}!",
                color=0x2ecc71
            )
            result_embed.set_image(url=DICE_FACE_URLS.get(result))
            
            # Edit to show result
            try:
                await rolling_msg.edit(embed=result_embed)
            except Exception:
                # Fallback: send new message if edit fails
                await interaction.followup.send(embed=result_embed)
            
            logger.info(f"🎲 {interaction.user.id} rolled a {result} on birthday message")
            
        except Exception as e:
            logger.error(f"❌ Error in birthday dice button: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ Failed to roll dice. Please try again!",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ Failed to roll dice. Please try again!",
                        ephemeral=True
                    )
            except:
                pass




class BirthdaySystem(commands.Cog):
    """Birthday management system with automatic birthday wishes"""


    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.birthdays_cache = {}
        self.sent_wishes_cache = {}  # Track sent wishes: {user_id: "YYYY-MM-DD"}
        self.birthday_channels_cache = {}  # Track birthday channels: {guild_id: channel_id}
        self.load_birthdays()
        self.load_sent_wishes()
        self.load_birthday_channels()
        # Start the daily birthday check task
        self.check_birthdays.start()
        logger.info("✅ Birthday System initialized")

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.check_birthdays.cancel()

    def load_birthday_channels(self):
        """Load birthday channels from JSON file"""
        try:
            if BIRTHDAY_CHANNELS_FILE.exists():
                with BIRTHDAY_CHANNELS_FILE.open('r', encoding='utf-8') as f:
                    self.birthday_channels_cache = json.load(f)
                logger.info(f"📺 Loaded {len(self.birthday_channels_cache)} birthday channel configurations")
            else:
                self.birthday_channels_cache = {}
                logger.info("📺 No birthday channels file found, starting fresh")
        except Exception as e:
            logger.error(f"❌ Failed to load birthday channels: {e}")
            self.birthday_channels_cache = {}

    def save_birthday_channels(self):
        """Save birthday channels to JSON file"""
        try:
            with BIRTHDAY_CHANNELS_FILE.open('w', encoding='utf-8') as f:
                json.dump(self.birthday_channels_cache, f, indent=2)
            logger.debug("💾 Saved birthday channels configuration")
        except Exception as e:
            logger.error(f"❌ Failed to save birthday channels: {e}")

    def get_birthday_channel(self, guild_id: int) -> Optional[int]:
        """Get birthday channel ID for a guild (MongoDB first, then JSON file, then env variable fallback)"""
        try:
            # Try MongoDB first (per-guild configuration)
            if mongo_enabled() and BirthdayChannelAdapter:
                channel_id = BirthdayChannelAdapter.get(guild_id)
                if channel_id:
                    return int(channel_id)
        except Exception as e:
            logger.debug(f"Failed to get birthday channel from MongoDB: {e}")
        
        # Try JSON file (per-guild configuration)
        try:
            guild_id_str = str(guild_id)
            if guild_id_str in self.birthday_channels_cache:
                return int(self.birthday_channels_cache[guild_id_str])
        except Exception as e:
            logger.debug(f"Failed to get birthday channel from JSON: {e}")
        
        # Fallback to environment variable (global configuration)
        try:
            env_channel = os.getenv('BIRTHDAY_CHANNEL_ID')
            if env_channel:
                return int(env_channel)
        except Exception as e:
            logger.debug(f"Failed to get birthday channel from env: {e}")
        
        return None

    def set_birthday_channel(self, guild_id: int, channel_id: int) -> bool:
        """Set birthday channel ID for a guild"""
        try:
            # Try MongoDB first
            if mongo_enabled() and BirthdayChannelAdapter:
                success = BirthdayChannelAdapter.set(guild_id, channel_id)
                if success:
                    logger.info(f"✅ Saved birthday channel {channel_id} for guild {guild_id} to MongoDB")
                    return True
        except Exception as e:
            logger.debug(f"Failed to save birthday channel to MongoDB: {e}")
        
        # Fallback to JSON file
        try:
            self.birthday_channels_cache[str(guild_id)] = channel_id
            self.save_birthday_channels()
            logger.info(f"✅ Saved birthday channel {channel_id} for guild {guild_id} to JSON")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save birthday channel: {e}")
            return False

    def load_birthdays(self):
        """Load birthdays from MongoDB or JSON file"""
        try:
            if mongo_enabled() and BirthdaysAdapter:
                self.birthdays_cache = BirthdaysAdapter.load_all()
                logger.info(f"📅 Loaded {len(self.birthdays_cache)} birthdays from MongoDB")
            else:
                if BIRTHDAYS_FILE.exists():
                    with BIRTHDAYS_FILE.open('r', encoding='utf-8') as f:
                        self.birthdays_cache = json.load(f)
                    logger.info(f"📅 Loaded {len(self.birthdays_cache)} birthdays from JSON")
                else:
                    self.birthdays_cache = {}
                    logger.info("📅 No birthdays file found, starting fresh")
        except Exception as e:
            logger.error(f"❌ Failed to load birthdays: {e}")
            self.birthdays_cache = {}

    def save_birthdays(self):
        """Save birthdays to JSON file (fallback only)"""
        try:
            if not mongo_enabled():
                with BIRTHDAYS_FILE.open('w', encoding='utf-8') as f:
                    json.dump(self.birthdays_cache, f, indent=2)
                logger.info("💾 Saved birthdays to JSON file")
        except Exception as e:
            logger.error(f"❌ Failed to save birthdays: {e}")

    def load_sent_wishes(self):
        """Load sent wishes tracking from JSON file"""
        try:
            if SENT_WISHES_FILE.exists():
                with SENT_WISHES_FILE.open('r', encoding='utf-8') as f:
                    self.sent_wishes_cache = json.load(f)
                logger.info(f"📋 Loaded {len(self.sent_wishes_cache)} sent wish records")
            else:
                self.sent_wishes_cache = {}
                logger.info("📋 No sent wishes file found, starting fresh")
        except Exception as e:
            logger.error(f"❌ Failed to load sent wishes: {e}")
            self.sent_wishes_cache = {}

    def save_sent_wishes(self):
        """Save sent wishes tracking to JSON file"""
        try:
            with SENT_WISHES_FILE.open('w', encoding='utf-8') as f:
                json.dump(self.sent_wishes_cache, f, indent=2)
            logger.debug("💾 Saved sent wishes tracking")
        except Exception as e:
            logger.error(f"❌ Failed to save sent wishes: {e}")

    def mark_wish_sent(self, user_id: int):
        """Mark a birthday wish as sent for today"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        user_id_str = str(user_id)
        self.sent_wishes_cache[user_id_str] = today
        self.save_sent_wishes()
        logger.debug(f"✅ Marked wish sent for user {user_id} on {today}")

    def was_wish_sent_today(self, user_id: int) -> bool:
        """Check if a birthday wish was already sent today"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        user_id_str = str(user_id)
        sent_date = self.sent_wishes_cache.get(user_id_str)
        return sent_date == today


    def add_birthday(self, user_id: int, day: int, month: int, player_id: Optional[str] = None) -> bool:
        """Add or update a user's birthday"""
        try:
            user_id_str = str(user_id)
            
            # Update cache
            birthday_data = {"day": day, "month": month}
            if player_id:
                birthday_data["player_id"] = player_id
            self.birthdays_cache[user_id_str] = birthday_data
            
            # Save to MongoDB or JSON
            if mongo_enabled() and BirthdaysAdapter:
                try:
                    # Try to save with player_id (new signature)
                    success = BirthdaysAdapter.set(user_id_str, day, month, player_id)
                except TypeError:
                    # Fallback for old MongoDB adapter that doesn't support player_id
                    logger.warning(f"MongoDB adapter doesn't support player_id yet, saving without it")
                    success = BirthdaysAdapter.set(user_id_str, day, month)
                
                if success:
                    logger.info(f"✅ Saved birthday for user {user_id} to MongoDB")
            else:
                self.save_birthdays()
                logger.info(f"✅ Saved birthday for user {user_id} to JSON")
                success = True
            
            # Check if birthday is today and send wish immediately if not already sent
            if success:
                now = datetime.utcnow()
                if day == now.day and month == now.month:
                    if not self.was_wish_sent_today(user_id):
                        # Schedule immediate wish sending
                        asyncio.create_task(self._send_immediate_birthday_wish(user_id))
                        logger.info(f"🎂 Birthday is today! Scheduling immediate wish for user {user_id}")
                    else:
                        logger.debug(f"⏭️ Birthday wish already sent today for user {user_id}")
            
            return success
        except Exception as e:
            logger.error(f"❌ Failed to add birthday for user {user_id}: {e}")
            return False

    def remove_birthday(self, user_id: int) -> bool:
        """Remove a user's birthday"""
        try:
            user_id_str = str(user_id)
            
            # Remove from cache
            if user_id_str in self.birthdays_cache:
                del self.birthdays_cache[user_id_str]
            
            # Remove from MongoDB or JSON
            if mongo_enabled() and BirthdaysAdapter:
                success = BirthdaysAdapter.remove(user_id_str)
                if success:
                    logger.info(f"✅ Removed birthday for user {user_id} from MongoDB")
                return success
            else:
                self.save_birthdays()
                logger.info(f"✅ Removed birthday for user {user_id} from JSON")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to remove birthday for user {user_id}: {e}")
            return False

    def get_birthday(self, user_id: int) -> Optional[dict]:
        """Get a user's birthday"""
        user_id_str = str(user_id)
        return self.birthdays_cache.get(user_id_str)

    def is_valid_date(self, day: int, month: int) -> bool:
        """Validate if the day and month form a valid date"""
        try:
            if month < 1 or month > 12:
                return False
            max_day = calendar.monthrange(2024, month)[1]  # Use 2024 (leap year) for Feb 29
            return 1 <= day <= max_day
        except Exception:
            return False

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize the daily check task when bot is ready"""
        if not hasattr(self, '_check_task_started'):
            self._check_task_started = True

    @tasks.loop(time=time(hour=0, minute=0))  # Run at 0:00 UTC daily
    async def check_birthdays(self):
        """Check for birthdays daily and send wishes at 0 UTC"""
        try:
            now = datetime.utcnow()
            today_day = now.day
            today_month = now.month
            
            logger.info(f"🎂 Checking birthdays for {today_month}/{today_day}")
            
            # Get birthday channel ID (per-guild or env fallback)
            # Note: Using guild ID from first birthday user's guild, or None if no users
            # This is a limitation - ideally we'd store guild_id with each birthday
            birthday_channel_id = None
            if self.birthdays_cache:
                # Try to get guild from bot's guilds
                for guild in self.bot.guilds:
                    birthday_channel_id = self.get_birthday_channel(guild.id)
                    if birthday_channel_id:
                        break
            
            if not birthday_channel_id:
                logger.warning("⚠️ No birthday channel configured for any guild")
                return
            
            try:
                channel = self.bot.get_channel(int(birthday_channel_id))
                if not channel:
                    logger.warning(f"⚠️ Birthday channel {birthday_channel_id} not found")
                    return
            except Exception as e:
                logger.error(f"❌ Failed to get birthday channel: {e}")
                return
            
            # Reload birthdays and sent wishes to get latest data
            self.load_birthdays()
            self.load_sent_wishes()
            
            # Find users with birthdays today who haven't received wishes yet
            birthday_users = []
            skipped_users = []
            
            for user_id_str, birthday_data in self.birthdays_cache.items():
                if birthday_data.get('day') == today_day and birthday_data.get('month') == today_month:
                    try:
                        user_id = int(user_id_str)
                        
                        # Check if wish was already sent today
                        if self.was_wish_sent_today(user_id):
                            skipped_users.append(user_id)
                            logger.debug(f"⏭️ Skipping user {user_id} - wish already sent today")
                            continue
                        
                        user = await self.bot.fetch_user(user_id)
                        if user:
                            birthday_users.append(user)
                    except Exception as e:
                        logger.error(f"❌ Failed to fetch user {user_id_str}: {e}")
            
            # Log skipped users
            if skipped_users:
                logger.info(f"⏭️ Skipped {len(skipped_users)} user(s) - wishes already sent today")
            
            # Send birthday wishes
            if birthday_users:
                await self.send_birthday_wishes(channel, birthday_users)
                # Mark wishes as sent
                for user in birthday_users:
                    self.mark_wish_sent(user.id)
                logger.info(f"🎉 Sent birthday wishes for {len(birthday_users)} user(s)")
            else:
                if not skipped_users:
                    logger.info("📅 No birthdays today")
                
        except Exception as e:
            logger.error(f"❌ Error in birthday check task: {e}")

    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        """Wait until bot is ready and calculate time until next 0 UTC"""
        await self.bot.wait_until_ready()
        
        # Calculate time until next 0:00 UTC
        now = datetime.utcnow()
        next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # If it's already past 0:00 UTC today, schedule for tomorrow
        if now.hour >= 0 and now.minute > 0:
            next_run += timedelta(days=1)
        
        wait_seconds = (next_run - now).total_seconds()
        
        logger.info(f"✅ Birthday check task ready - next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logger.info(f"⏰ Waiting {wait_seconds/3600:.1f} hours until next check")

    async def _send_immediate_birthday_wish(self, user_id: int):
        """Send birthday wish immediately for a user whose birthday is today"""
        try:
            # Get birthday channel
            # Get birthday channel for this guild
            guild_id = None
            for guild in self.bot.guilds:
                birthday_channel_id = self.get_birthday_channel(guild.id)
                if birthday_channel_id:
                    break
            
            if not birthday_channel_id:
                logger.warning("⚠️ No birthday channel configured, cannot send immediate wish")
                return
            
            channel = self.bot.get_channel(int(birthday_channel_id))
            if not channel:
                logger.warning(f"⚠️ Birthday channel {birthday_channel_id} not found")
                return
            
            # Fetch user
            user = await self.bot.fetch_user(user_id)
            if not user:
                logger.error(f"❌ Could not fetch user {user_id} for immediate birthday wish")
                return
            
            # Send wish
            await self.send_birthday_wishes(channel, [user])
            
            # Mark as sent
            self.mark_wish_sent(user_id)
            
            logger.info(f"🎉 Sent immediate birthday wish for user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send immediate birthday wish for user {user_id}: {e}")


    async def send_birthday_wishes(self, channel: discord.TextChannel, users: list):
        """Send birthday wishes to the channel"""
        try:
            # Import WOS API function
            from wos_api import fetch_player_info
            
            # Get server name
            server_name = channel.guild.name if channel.guild else "Whiteout Survival"
            
            # Create celebratory embed
            embed = discord.Embed(
                title="🎉 Happy Birthday! 🎂",
                description="",
                color=0xFF69B4  # Hot pink
            )
            
            # Add birthday users
            mentions = []
            for user in users:
                mentions.append(user.mention)
            
            if len(users) == 1:
                embed.description = (
                    f"Wishing {mentions[0]} an amazing day! 🎈\n\n"
                    f"May your day be filled with joy, laughter, and wonderful moments! 🌟\n\n"
                    f"— From **{server_name}** & **Whiteout Survival** 🎊"
                )
                
                # Try to get WOS avatar if player_id is available
                wos_avatar_url = None
                user_id_str = str(users[0].id)
                birthday_data = self.birthdays_cache.get(user_id_str, {})
                player_id = birthday_data.get('player_id')
                
                logger.info(f"🔍 Birthday data for user {users[0].id}: {birthday_data}")
                logger.info(f"🔍 Player ID found: {player_id}")
                
                if player_id:
                    try:
                        logger.info(f"🌐 Fetching WOS player info for player_id: {player_id}")
                        # Fetch player info from WOS API
                        player_info = await fetch_player_info(player_id)
                        logger.info(f"🌐 WOS API response: {player_info}")
                        if player_info and player_info.get('avatar_image'):
                            wos_avatar_url = player_info['avatar_image']
                            logger.info(f"✅ Using WOS avatar as thumbnail for user {users[0].id}: {wos_avatar_url}")
                        else:
                            logger.warning(f"⚠️ No avatar_image in WOS API response for player {player_id}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch WOS avatar for player {player_id}: {e}")
                else:
                    logger.info(f"ℹ️ No player_id found for user {users[0].id}, using Discord avatar only")
                
                # Always use Discord avatar in author field (circular)
                embed.set_author(
                    name=f"🎂 {users[0].display_name}'s Birthday",
                    icon_url=users[0].display_avatar.url
                )
                
                # Use WOS avatar as thumbnail if available, otherwise use Discord avatar
                if wos_avatar_url:
                    embed.set_thumbnail(url=wos_avatar_url)
                    logger.info(f"✅ Set WOS avatar as thumbnail")
                else:
                    embed.set_thumbnail(url=users[0].display_avatar.url)
                    logger.info(f"ℹ️ Set Discord avatar as thumbnail (no WOS avatar available)")
                
                # Add player ID field if available
                if player_id:
                    embed.add_field(
                        name="🎮 Player ID",
                        value=f"`{player_id}`",
                        inline=False
                    )
            else:
                embed.description = (
                    f"Wishing {', '.join(mentions)} a very **Happy Birthday**! 🎈\n\n"
                    f"May your day be filled with joy, laughter, and wonderful moments! 🌟\n\n"
                    f"— From **{server_name}** & **Whiteout Survival** 🎊"
                )
                # For multiple birthdays, use the birthday cake GIF
                embed.set_thumbnail(url="https://i.imgur.com/9KWzH9s.gif")
            
            embed.set_footer(
                text=f"🎂 Birthday on {datetime.utcnow().strftime('%B %d')}",
                icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1436745053442805830/unnamed_5.png?ex=6933a85a&is=693256da&hm=75ec361677f174173e526863fdaa30d9b3e6983f9f1ad45dd1a9601aad6c0021"
            )
            
            # Create persistent view with wish button
            user_ids = [user.id for user in users]
            view = BirthdayWishView(user_ids)
            
            # Send the message with the button
            await channel.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"❌ Failed to send birthday wishes: {e}")

    async def manual_birthday_check(self, channel: discord.TextChannel):
        """Manually trigger birthday check (for testing)"""
        try:
            now = datetime.utcnow()
            today_day = now.day
            today_month = now.month
            
            logger.info(f"🧪 Manual birthday check for {today_month}/{today_day}")
            
            # Reload birthdays to get latest data
            self.load_birthdays()
            
            # Find users with birthdays today
            birthday_users = []
            for user_id_str, birthday_data in self.birthdays_cache.items():
                if birthday_data.get('day') == today_day and birthday_data.get('month') == today_month:
                    try:
                        user_id = int(user_id_str)
                        user = await self.bot.fetch_user(user_id)
                        if user:
                            birthday_users.append(user)
                    except Exception as e:
                        logger.error(f"❌ Failed to fetch user {user_id_str}: {e}")
            
            # Send birthday wishes
            if birthday_users:
                await self.send_birthday_wishes(channel, birthday_users)
                logger.info(f"🎉 Sent birthday wishes for {len(birthday_users)} user(s)")
                return True, len(birthday_users)
            else:
                logger.info("📅 No birthdays today")
                return False, 0
                
        except Exception as e:
            logger.error(f"❌ Error in manual birthday check: {e}")
            return False, 0


async def setup(bot: commands.Bot):
    """Setup function to load the cog"""
    await bot.add_cog(BirthdaySystem(bot))
    logger.info("✅ Birthday System cog loaded")
