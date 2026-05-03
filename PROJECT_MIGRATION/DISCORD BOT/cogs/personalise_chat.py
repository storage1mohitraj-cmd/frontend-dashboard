"""
Personalised Chat Command - /personalisechat

This cog provides a multi-step interaction flow to collect user preferences:
1. Pronoun selection
2. Personality trait selection (up to 3)
3. Player ID input

After collecting preferences, it fetches player data and generates a personalized
response using OpenRouter.
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
import hashlib
import time
import aiohttp
import ssl
import re
from typing import Optional, List

from angel_personality import angel_personality
from api_manager import make_request
from command_animator import command_animation

logger = logging.getLogger(__name__)

# Player API endpoint and secret (same as playerinfo.py)
API_URL = "https://wos-giftcode-api.centurygame.com/api/player"
SECRET = "tB87#kPtkxqOS2"

# Personality trait options
PERSONALITY_TRAITS = [
    "Friendly",
    "Competitive",
    "Strategic",
    "Helpful",
    "Casual",
    "Serious",
    "Humorous",
    "Analytical",
    "Creative",
    "Adventurous"
]


class PronounSelectView(discord.ui.View):
    """Step 1: Pronoun selection"""
    
    def __init__(self, user_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.selected_pronouns = None
    
    @discord.ui.select(
        placeholder="👤 Step 1: Your Pronouns - How should the bot refer to you?",
        options=[
            discord.SelectOption(label="He/Him", value="he/him", emoji="👨"),
            discord.SelectOption(label="She/Her", value="she/her", emoji="👩"),
            discord.SelectOption(label="They/Them", value="they/them", emoji="🧑"),
            discord.SelectOption(label="Other", value="other", emoji="✨"),
        ]
    )
    async def pronoun_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This is not your personalization session.", ephemeral=True)
            return
        
        self.selected_pronouns = select.values[0]
        
        # Move to Step 2: Personality traits
        trait_view = TraitSelectView(self.user_id, self.selected_pronouns)
        
        embed = discord.Embed(
            title="✨ Step 2: Bot's Traits",
            description="Select up to 3 personality traits that describe you best.\nThis helps the bot personalize responses to match your style!",
            color=0x9b59b6
        )
        embed.add_field(
            name="📝 Selected Pronouns",
            value=f"`{self.selected_pronouns}`",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=trait_view)


class TraitSelectView(discord.ui.View):
    """Step 2: Personality trait selection (up to 3)"""
    
    def __init__(self, user_id: str, pronouns: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.pronouns = pronouns
        self.selected_traits = []
    
    @discord.ui.select(
        placeholder="✨ Select up to 3 personality traits",
        options=[
            discord.SelectOption(label=trait, value=trait.lower())
            for trait in PERSONALITY_TRAITS
        ],
        min_values=1,
        max_values=3
    )
    async def trait_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This is not your personalization session.", ephemeral=True)
            return
        
        self.selected_traits = select.values
        
        # Move to Step 3: Player ID input
        player_id_modal = PlayerIDModal(self.user_id, self.pronouns, self.selected_traits)
        await interaction.response.send_modal(player_id_modal)


class PlayerIDModal(discord.ui.Modal, title="🎮 Step 3: Player Information"):
    """Step 3: Player ID input"""
    
    player_id = discord.ui.TextInput(
        label="Player ID (9 digits)",
        placeholder="Enter your 9-digit player ID",
        required=True,
        min_length=9,
        max_length=9
    )
    
    def __init__(self, user_id: str, pronouns: str, traits: List[str]):
        super().__init__()
        self.user_id = user_id
        self.pronouns = pronouns
        self.traits = traits
    
    async def on_submit(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This is not your personalization session.", ephemeral=True)
            return
        
        player_id = self.player_id.value.strip()
        
        # Validate player ID format
        if not re.fullmatch(r"\d{9}", player_id):
            await interaction.response.send_message(
                "❌ Invalid player ID. Must be exactly 9 digits.",
                ephemeral=True
            )
            return
        
        # Defer response while we validate player ID
        await interaction.response.defer(thinking=True)
        
        try:
            # Validate player ID by fetching data from API
            player_data = await self.fetch_player_data(player_id)
            
            if not player_data:
                await interaction.followup.send(
                    "❌ Could not validate player ID. Please check your player ID and try again.",
                    ephemeral=True
                )
                return
            
            # Get current player info for display (but don't store it)
            player_name = player_data.get('nickname', 'Unknown')
            furnace_level = player_data.get('furnace_level', 0)
            state_id = player_data.get('kid', 'N/A')
            
            # Update user profile in angel_personality
            user_name = interaction.user.display_name or interaction.user.name
            profile = angel_personality.get_user_profile(self.user_id, user_name)
            
            # Store ONLY player_id and preferences (not the player data itself)
            angel_personality.update_user_profile(self.user_id, {
                'gender': self.get_gender_from_pronouns(self.pronouns),
                'personality_traits': self.traits,
                'game_progress': {
                    'player_id': player_id  # Only store the ID, not the data
                }
            })
            
            # Save profiles
            angel_personality.save_profiles()
            
            # Generate personalized response using OpenRouter
            personalized_response = await self.generate_personalized_response(
                user_name, player_name, furnace_level, self.pronouns, self.traits
            )
            
            # Create success embed showing current stats (fetched live)
            embed = discord.Embed(
                title="✅ Personalization Complete!",
                description=personalized_response,
                color=0x2ecc71
            )
            embed.add_field(name="👤 Pronouns", value=f"`{self.pronouns}`", inline=True)
            embed.add_field(name="✨ Traits", value=f"`{', '.join(self.traits)}`", inline=True)
            embed.add_field(name="🎮 Player ID", value=f"`{player_id}`", inline=True)
            embed.add_field(name="📊 Current Stats", value=f"**{player_name}** • FC {furnace_level} • State {state_id}", inline=False)
            embed.set_footer(text="Your player ID is saved! I'll fetch fresh data whenever you ask about your game stats.")
            
            await interaction.followup.send(embed=embed)
            
            logger.info(f"Personalization completed for user {self.user_id}: pronouns={self.pronouns}, traits={self.traits}, player_id={player_id}")
            
        except Exception as e:
            logger.error(f"Error in personalization flow: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ An error occurred during personalization: {str(e)}",
                ephemeral=True
            )
    
    async def fetch_player_data(self, player_id: str) -> Optional[dict]:
        """Fetch player data from WOS API"""
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://wos-giftcode-api.centurygame.com",
            }
            
            current_time = int(time.time() * 1000)
            form = f"fid={player_id}&time={current_time}"
            sign = hashlib.md5((form + SECRET).encode("utf-8")).hexdigest()
            payload = f"sign={sign}&{form}"
            
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                async with session.post(API_URL, data=payload, headers=headers, timeout=20) as resp:
                    try:
                        js = await resp.json()
                    except Exception:
                        logger.warning(f"Invalid JSON response for player ID {player_id}")
                        return None
                    
                    if js.get("code") != 0:
                        logger.warning(f"API error for player ID {player_id}: {js.get('msg')}")
                        return None
                    
                    data = js.get('data', {})
                    return {
                        'nickname': data.get('nickname', 'Unknown'),
                        'furnace_level': int(data.get('stove_lv', 0)) if data.get('stove_lv') else 0,
                        'kid': data.get('kid', 'N/A')
                    }
        
        except Exception as e:
            logger.error(f"Error fetching player data for {player_id}: {e}")
            return None
    
    def get_gender_from_pronouns(self, pronouns: str) -> str:
        """Convert pronouns to gender for angel_personality system"""
        if pronouns == "he/him":
            return "male"
        elif pronouns == "she/her":
            return "female"
        else:
            return "unknown"
    
    async def generate_personalized_response(
        self, user_name: str, player_name: str, furnace_level: int, 
        pronouns: str, traits: List[str]
    ) -> str:
        """Generate a personalized greeting using OpenRouter"""
        try:
            # Create a personalized system prompt
            system_prompt = f"""You are Molly, a friendly Discord bot for Whiteout Survival.
You're welcoming a new user who just personalized their chat experience.

User Details:
- Discord Name: {user_name}
- Player Name: {player_name}
- Furnace Level: {furnace_level}
- Pronouns: {pronouns}
- Personality Traits: {', '.join(traits)}

Generate a warm, personalized welcome message (2-3 sentences) that:
1. Acknowledges their personality traits
2. References their game progress (furnace level)
3. Makes them feel special and welcomed
4. Uses appropriate pronouns

Keep it friendly, enthusiastic, and tailored to their traits!"""
            
            user_message = "Welcome me to the personalized chat experience!"
            
            response = await make_request(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            
            if response and response.strip():
                return response.strip()
            else:
                # Fallback message if OpenRouter fails
                return f"Welcome, {player_name}! 🎉 I've saved your preferences and I'm excited to chat with you. With a furnace level of {furnace_level}, you're doing great! Let's make our conversations awesome together! 🚀"
        
        except Exception as e:
            logger.error(f"Error generating personalized response: {e}")
            # Fallback message
            return f"Welcome, {player_name}! 🎉 Your preferences have been saved. I'm here to help with all your Whiteout Survival questions!"


class PersonaliseChatCog(commands.Cog):
    """Cog for the /personalisechat command"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("PersonaliseChatCog initialized")
    
    @app_commands.command(
        name="personalisechat",
        description="Personalize your chat experience with the bot"
    )
    @command_animation
    async def personalisechat(self, interaction: discord.Interaction):
        """Main command to start the personalization flow"""
        try:
            user_id = str(interaction.user.id)
            
            # Create initial embed
            embed = discord.Embed(
                title="🎨 Personalize Your Chat Experience",
                description=(
                    "Let's make our conversations more personal! 🌟\n\n"
                    "I'll ask you a few quick questions to understand you better:\n"
                    "1️⃣ **Your Pronouns** - How should I refer to you?\n"
                    "2️⃣ **Your Personality** - What traits describe you?\n"
                    "3️⃣ **Your Game Info** - Your player details\n\n"
                    "This helps me tailor responses just for you! 💬"
                ),
                color=0x3498db
            )
            embed.set_footer(text="Click the dropdown below to get started!")
            
            # Create Step 1 view
            view = PronounSelectView(user_id)
            
            # Check if interaction was already responded to (deferred)
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error in /personalisechat command: {e}", exc_info=True)
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ An error occurred while starting personalization. Please try again.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ An error occurred while starting personalization. Please try again.",
                    ephemeral=True
                )


async def setup(bot: commands.Bot):
    """Add the cog to the bot"""
    await bot.add_cog(PersonaliseChatCog(bot))
