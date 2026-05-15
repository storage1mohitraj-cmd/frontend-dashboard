import discord
import logging
from discord.ext import commands
from event_tips import EVENT_TIPS, get_event_info, get_all_categories, get_difficulty_color, get_category_emoji
from command_animator import command_animation

logger = logging.getLogger(__name__)


class EventsCog(commands.Cog):
    """Cog for event information commands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("EventsCog initialized")

    @discord.slash_command(name="event", description="Get information about Whiteout Survival events")
    @command_animation
    async def event(self, interaction: discord.ApplicationContext, event_name: str):
        """Handle the event command"""
        logger.info(f"Event command called with event_name: {event_name}")

        # Show specific event info
        event_info = get_event_info(event_name.lower())
        if not event_info:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Event '{0}' not found. Available events: bear, foundry, crazyjoe, alliancemobilization, alliancechampionship, canyonclash, fishingtournament, frostfiremine".format(event_name),
                    ephemeral=True)
            else:
                await interaction.response.send_message(
                    "❌ Event '{0}' not found. Available events: bear, foundry, crazyjoe, alliancemobilization, alliancechampionship, canyonclash, fishingtournament, frostfiremine".format(event_name),
                    ephemeral=True)
            return

        # Build simple description
        description_lines = []

        if event_info.get('guide'):
            description_lines.append(f"📚 Guide: [Click here]({event_info['guide']})")

        if event_info.get('video'):
            description_lines.append(f"🎥 Video Guide: [Watch here]({event_info['video']})")

        if event_info.get('tips'):
            description_lines.append(f"💡 Tips: {event_info['tips']}")
        else:
            description_lines.append("💡 Tips: please wait🙏- working on it.....")

        description = "\n".join(description_lines) if description_lines else "No information available."

        embed = discord.Embed(
            title=f"{get_category_emoji(event_info['category'])} {event_info['name']}",
            description=description,
            color=get_difficulty_color(event_info['difficulty']))

        if 'image' in event_info:
            embed.set_thumbnail(url=event_info['image'])

        # Check if interaction was already responded to (deferred)
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)


def setup(bot):
    """Required setup function for loading the cog"""
    bot.add_cog(EventsCog(bot))
    logger.info("EventsCog loaded successfully")
