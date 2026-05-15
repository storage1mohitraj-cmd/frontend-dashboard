"""
Web Search Cog
Allows searching the web using Google Search API.
"""

import discord
from discord.ext import commands
import aiohttp
import os
import logging
from typing import Optional, List
from command_animator import command_animation

logger = logging.getLogger(__name__)

class WebSearch(commands.Cog):
    """Cog for web searching functionality"""

    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.search_engine_id = os.getenv("GOOGLE_CSE_ID")

    @discord.slash_command(
        name="google",
        description="Search Google for information"
    )
    @command_animation
    async def google_search(
        self,
        interaction: discord.ApplicationContext,
        query: str
    ):
        """Search Google."""
        if not self.api_key or not self.search_engine_id:
            await interaction.response.send_message(
                "❌ Google Search API not configured. Please set GOOGLE_API_KEY and GOOGLE_CSE_ID.",
                ephemeral=True
            )
            return

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'q': query,
            'key': self.api_key,
            'cx': self.search_engine_id,
            'num': 5
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        await interaction.response.send_message(
                            f"❌ Search failed with status {resp.status}",
                            ephemeral=True
                        )
                        return

                    data = await resp.json()
                    items = data.get('items', [])

                    if not items:
                        await interaction.response.send_message(
                            f"🔍 No results found for: **{query}**",
                            ephemeral=True
                        )
                        return

                    embed = discord.Embed(
                        title=f"🔍 Search Results: {query[:50]}",
                        color=discord.Color.blue(),
                        url=f"https://www.google.com/search?q={query.replace(' ', '+')}"
                    )

                    for item in items[:5]:
                        title = item.get('title', 'No Title')
                        link = item.get('link', '#')
                        snippet = item.get('snippet', 'No description available.')
                        embed.add_field(
                            name=title,
                            value=f"[Link]({link})\n{snippet}",
                            inline=False
                        )

                    embed.set_footer(text="Powered by Google Custom Search")
                    await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Search error: {e}")
            await interaction.followup.send(
                f"❌ An error occurred during search: {str(e)}",
                ephemeral=True
            )


def setup(bot):
    """Setup function to add the cog to the bot."""
    bot.add_cog(WebSearch(bot))
