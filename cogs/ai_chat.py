import discord
from discord.ext import commands
import logging

try:
    from api_manager import make_request
except ImportError:
    make_request = None
    logging.warning("api_manager could not be imported. AI responses will be disabled.")

logger = logging.getLogger(__name__)

class WelcomeView(discord.ui.View):
    """View containing the Personalise button for the greeting message."""
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Personalise", style=discord.ButtonStyle.primary, emoji="🎨", custom_id="welcome_personalise")
    async def personalise(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Trigger the personalization flow."""
        try:
            # Import here to avoid circular dependencies
            from cogs.personalise_chat import PronounSelectView
            
            user_id = str(interaction.user.id)
            
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
            
            view = PronounSelectView(user_id)
            # Use ephemeral=True so other users don't see the flow
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in WelcomeView button: {e}", exc_info=True)
            await interaction.response.send_message("❌ An error occurred. Please try using `/personalisechat` instead.", ephemeral=True)

class AIChat(commands.Cog):
    """Cog for AI chat functionality on mentions, replies, and DMs."""
    
    def __init__(self, bot):
        self.bot = bot
        # Register the view for persistence
        self.bot.add_view(WelcomeView())
        
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Send a greeting when joining a new server."""
        # Find a suitable channel
        chat_channel = None
        
        # Priority 1: Substring match for common channel names
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                channel_name = channel.name.lower()
                if any(word in channel_name for word in ["chat", "general", "main", "welcome"]):
                    chat_channel = channel
                    break
                    
        # Priority 2: Use the system channel if we have permission
        if not chat_channel and guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            chat_channel = guild.system_channel
            
        # Priority 3: Fallback to the very first channel we have permission to type in
        if not chat_channel:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    chat_channel = channel
                    break
                    
        if chat_channel:
            try:
                embed = discord.Embed(
                    title="👋 Hello there!",
                    description=(
                        f"I'm **{self.bot.user.name}**, your friendly AI assistant!\n\n"
                        "💬 **How to talk to me:**\n"
                        "• Tag me in a message (e.g., `@Molly how do I...`)\n"
                        "• Reply to any of my messages\n"
                        "• Send me a Direct Message (DM)"
                    ),
                    color=discord.Color.blue()
                )
                await chat_channel.send(embed=embed, view=WelcomeView())
                logger.info(f"[AIChat] Sent welcome message to {guild.name} in {chat_channel.name}")
            except Exception as e:
                logger.error(f"[AIChat] Failed to send welcome message to {guild.name}: {e}")

async def setup(bot):
    await bot.add_cog(AIChat(bot))
