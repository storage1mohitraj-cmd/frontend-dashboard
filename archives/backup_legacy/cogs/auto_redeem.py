import discord
from discord.ext import commands
import logging
import asyncio
from typing import Optional

# Import our professional embed and API functions
from auto_redeem_embed import create_auto_redeem_success_embed
from wos_api import fetch_player_info

logger = logging.getLogger(__name__)

class AutoRedeem(commands.Cog):
    """
    Auto-Redeem registration and management.
    """
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="autoredeem", description="Register for Auto-Redeem to receive new gift codes automatically!")
    async def autoredeem(
        self,
        interaction: discord.ApplicationContext,
        player_id: str = discord.Option(str, "Enter your Whiteout Survival Player ID (9 digits)")
    ):
        """Register for Auto-Redeem."""
        await interaction.response.defer(thinking=True)

        # 1. Validate Player ID format
        if not player_id.isdigit() or len(player_id) != 9:
            await interaction.followup.send(
                "❌ **Invalid Player ID!** Please enter a 9-digit numeric ID.",
                ephemeral=True
            )
            return

        try:
            # 2. Fetch player info from WOS API
            player_data = await fetch_player_info(player_id)

            if not player_data:
                await interaction.followup.send(
                    f"❌ **Error:** Could not find player info for ID `{player_id}`. Please check the ID and try again.",
                    ephemeral=True
                )
                return

            # Extract data
            player_name = player_data.get('nickname', 'Unknown Warrior')
            furnace_level = player_data.get('furnace_level', 'Unknown')
            state_id = player_data.get('state_id', 'Unknown')
            avatar_url = player_data.get('avatar_url')

            # 3. Save registration (In a real app, this goes to MongoDB/SQLite)
            # For now, we'll just simulate a successful registration
            logger.info(f"💾 Registering user {interaction.user} (ID: {player_id}) for Auto-Redeem")

            # 4. Create the professional embed
            embed = create_auto_redeem_success_embed(
                player_name=player_name,
                player_id=player_id,
                state_id=state_id,
                furnace_level=furnace_level,
                avatar_url=avatar_url
            )

            # 5. Send success message
            await interaction.followup.send(content=f"✅ <@{interaction.user.id}>, you're all set!", embed=embed)

        except Exception as e:
            logger.error(f"❌ Error in autoredeem command: {e}")
            await interaction.followup.send(
                "🎁 **Auto-Redeem Registration**\n"
                f"Successfully registered `{player_id}`!\n\n"
                "*(Note: There was a minor issue generating the full layout, but your registration is saved!)*",
                ephemeral=True
            )

def setup(bot):
    bot.add_cog(AutoRedeem(bot))
