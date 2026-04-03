import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from command_animator import command_animation

try:
    from duckduckgo_search import DDGS
except Exception:
    DDGS = None


class WebSearch(commands.Cog):
    """Enhanced web search cog using duckduckgo-search.

    Provides a slash command `/websearch` that returns organized search results in rich embeds.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="websearch", description="Search the web with powerful, organized results")
    @app_commands.describe(
        query="Search query",
        max_results="Number of results (1-10)",
        region="Region code (e.g., us-en, uk-en, wt-wt for global)",
        safesearch="Safe search filter: off, moderate, or strict"
    )
    @app_commands.choices(safesearch=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Moderate", value="moderate"),
        app_commands.Choice(name="Strict", value="strict")
    ])
    @command_animation
    async def websearch(
        self,
        interaction: discord.Interaction,
        query: str,
        max_results: int = 5,
        region: str = "wt-wt",
        safesearch: str = "moderate"
    ):
        if DDGS is None:
            embed = discord.Embed(
                title="❌ Search Unavailable",
                description="The search integration is not available. Please install `duckduckgo-search`.",
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Clamp max_results to 1-10 range
        max_results = max(1, min(10, max_results))

        loop = asyncio.get_event_loop()

        try:
            # DDGS is synchronous/blocking; run in executor
            def _sync_search(q, mx, reg, safe):
                try:
                    ddgs = DDGS()
                    results = ddgs.text(q, region=reg, safesearch=safe, max_results=mx)
                    return list(results) if results else []
                except Exception as e:
                    print(f"Search error: {e}")
                    return []

            # Fetch search results
            results = await loop.run_in_executor(None, lambda: _sync_search(query, max_results, region, safesearch))
            instant_answers = []  # Instant answers not available in current version

            # Create rich embed with results
            embed = discord.Embed(
                title=f"🔍 Web Search Results",
                description=f"**Query:** {query}\n**Region:** {region} | **Safe Search:** {safesearch.capitalize()}",
                color=0x00D9FF  # Cyan color
            )

            # Add instant answer if available
            if instant_answers:
                answer_text = ""
                for answer in instant_answers[:1]:  # Usually just one answer
                    text = answer.get("text", "")
                    url = answer.get("url", "")
                    
                    if text:
                        answer_text = text
                        if url:
                            answer_text += f"\n\n[📖 Source]({url})"
                
                if answer_text:
                    embed.add_field(
                        name="💡 Instant Answer",
                        value=answer_text[:1024],
                        inline=False
                    )
                    # Add separator
                    embed.add_field(name="\u200b", value="**Search Results:**", inline=False)

            if not results and not instant_answers:
                embed = discord.Embed(
                    title="🔍 No Results Found",
                    description=f"No results found for: **{query}**\n\nTry different keywords or check your spelling.",
                    color=discord.Color.orange()
                )
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            for idx, r in enumerate(results[:max_results], start=1):
                title = r.get("title") or r.get("text") or "(no title)"
                href = r.get("href") or r.get("url") or r.get("link") or ""
                snippet = r.get("body") or r.get("snippet") or ""

                # Truncate snippet intelligently
                if len(snippet) > 150:
                    snippet = snippet[:147] + "..."

                # Format field value with snippet and link
                field_value = f"{snippet}\n[🔗 Visit Page]({href})" if href else snippet

                # Add numbered field for each result
                embed.add_field(
                    name=f"{idx}. {title[:100]}",
                    value=field_value[:1024],  # Discord field value limit
                    inline=False
                )

            # Add footer with result count
            embed.set_footer(text=f"Showing {len(results[:max_results])} of {len(results)} results")
            embed.timestamp = discord.utils.utcnow()

            if interaction.response.is_done():
                await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Search Failed",
                description=f"An error occurred while searching:\n```{str(e)}```",
                color=discord.Color.red()
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WebSearch(bot))
