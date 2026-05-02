import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from command_animator import command_animation

try:
    from duckduckgo_search import DDGS
except Exception:
    DDGS = None

try:
    from api_manager import make_request
except ImportError:
    make_request = None

import logging
logger = logging.getLogger(__name__)

# ─── Pagination View ──────────────────────────────────────────────────────────

class SearchResultsView(discord.ui.View):
    """Paginated view for raw search result links."""

    def __init__(self, results: list, query: str, per_page: int = 5):
        super().__init__(timeout=120)
        self.results = results
        self.query = query
        self.per_page = per_page
        self.page = 0
        self.total_pages = max(1, (len(results) + per_page - 1) // per_page)
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.total_pages - 1
        self.page_label.label = f"Page {self.page + 1}/{self.total_pages}"

    def _build_embed(self) -> discord.Embed:
        start = self.page * self.per_page
        end = start + self.per_page
        slice_ = self.results[start:end]

        embed = discord.Embed(
            title=f"🔗 Search Sources — Page {self.page + 1}/{self.total_pages}",
            description=f"**Query:** `{self.query}`",
            color=0x5865F2,
        )
        for idx, r in enumerate(slice_, start=start + 1):
            title = (r.get("title") or "(no title)")[:80]
            href = r.get("href") or r.get("url") or r.get("link") or ""
            snippet = (r.get("body") or r.get("snippet") or "")[:200]
            if len(snippet) == 200:
                snippet += "…"
            field_val = f"{snippet}\n[🌐 Open Link]({href})" if href else snippet
            embed.add_field(name=f"{idx}. {title}", value=field_val or "No preview.", inline=False)

        embed.set_footer(text=f"Powered by DuckDuckGo • {len(self.results)} results total")
        embed.timestamp = discord.utils.utcnow()
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="ws_prev")
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.primary, disabled=True, custom_id="ws_page")
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # Label only

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="ws_next")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.total_pages - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)


# ─── Cog ──────────────────────────────────────────────────────────────────────

class WebSearch(commands.Cog):
    """AI-powered web search cog.

    Fetches DuckDuckGo results, synthesizes an intelligent answer via the
    configured LLM, and presents it alongside paginated source links.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _run_ddg_text(query: str, max_results: int, region: str, safesearch: str) -> list:
        """Text search with multi-backend fallback (api → lite → html)."""
        import time
        backends = ["api", "lite", "html"]
        for backend in backends:
            for attempt in range(2):
                try:
                    logger.info(f"[WebSearch] text backend='{backend}' attempt={attempt+1}")
                    ddgs = DDGS()
                    try:
                        results = list(ddgs.text(
                            query, region=region, safesearch=safesearch,
                            max_results=max_results, backend=backend
                        ) or [])
                    except TypeError:
                        # Older DDGS — no backend param
                        results = list(ddgs.text(
                            query, region=region, safesearch=safesearch,
                            max_results=max_results
                        ) or [])
                    if results:
                        logger.info(f"[WebSearch] text backend='{backend}' → {len(results)} results")
                        return results
                    logger.warning(f"[WebSearch] text backend='{backend}' attempt {attempt+1} → 0 results")
                except Exception as e:
                    logger.warning(f"[WebSearch] text backend='{backend}' attempt {attempt+1} error: {e}")
                    if attempt == 0:
                        time.sleep(1)
        return []

    @staticmethod
    def _run_ddg_news(query: str, max_results: int, region: str, safesearch: str) -> list:
        """News search — better for current events/facts."""
        try:
            ddgs = DDGS()
            results = list(ddgs.news(
                query, region=region, safesearch=safesearch, max_results=max_results
            ) or [])
            # Normalize news fields to match text result schema
            normalized = []
            for r in results:
                normalized.append({
                    "title": r.get("title", ""),
                    "href": r.get("url") or r.get("href", ""),
                    "body": r.get("body") or r.get("excerpt", ""),
                    "_source": "news",
                })
            logger.info(f"[WebSearch] news → {len(normalized)} results")
            return normalized
        except Exception as e:
            logger.warning(f"[WebSearch] news search error: {e}")
            return []

    @staticmethod
    def _merge_results(text_results: list, news_results: list, max_total: int) -> list:
        """Merge text + news results, deduplicate by URL, news first for recency."""
        seen_urls = set()
        merged = []
        for r in news_results + text_results:
            url = (r.get("href") or r.get("url", "")).rstrip("/")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            merged.append(r)
            if len(merged) >= max_total:
                break
        return merged

    def _run_ddg(self, query: str, max_results: int, region: str, safesearch: str) -> list:
        """Run text + news searches and return merged deduplicated results."""
        text = self._run_ddg_text(query, max_results, region, safesearch)
        news = self._run_ddg_news(query, max_results // 2 + 1, region, safesearch)
        merged = self._merge_results(text, news, max_results)
        logger.info(f"[WebSearch] merged: {len(text)} text + {len(news)} news → {len(merged)} total")
        return merged

    @staticmethod
    def _build_ai_prompt(query: str, results: list) -> list:
        """Build the message list for the LLM synthesis call.

        The AI uses its own knowledge as primary source, grounded/verified
        by the search snippets. This ensures good answers even when DDG
        returns low-quality or outdated pages.
        """
        snippets = []
        for i, r in enumerate(results, 1):
            title = r.get("title") or ""
            body = (r.get("body") or r.get("snippet") or "")[:400]
            url = r.get("href") or r.get("url") or ""
            source_tag = "[NEWS]" if r.get("_source") == "news" else "[WEB]"
            snippets.append(f"[{i}]{source_tag} {title}\n{body}\nURL: {url}")

        search_context = "\n\n".join(snippets) if snippets else "(no snippets retrieved)"

        system = (
            "You are a knowledgeable AI assistant. Answer user queries accurately and directly.\n\n"
            "You have access to web search snippets to help ground your answer in current information. "
            "Follow these rules:\n"
            "• Give a direct, confident answer using your knowledge combined with the search snippets.\n"
            "• Prefer information from [NEWS] tagged snippets for current events — they are more recent.\n"
            "• Cite snippets inline as [1], [2], etc. ONLY when they directly support a specific claim.\n"
            "• If snippets contradict your knowledge, trust the snippets (they are more current).\n"
            "• If snippets are irrelevant or low quality, rely on your training knowledge and say so briefly.\n"
            "• Keep the answer under 350 words. Use bullet points for lists, short paragraphs for explanations.\n"
            "• Do NOT start your answer with 'Based on the provided snippets' — just answer directly.\n"
            "• End with a bold '**Key Takeaway:**' one-liner."
        )
        user_msg = (
            f"Query: {query}\n\n"
            f"Search Snippets (use for grounding and citations):\n{search_context}\n\n"
            "Answer the query directly and confidently."
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]

    @staticmethod
    def _chunk_text(text: str, max_len: int = 1024) -> list[str]:
        """Split text into Discord-safe chunks."""
        chunks = []
        while len(text) > max_len:
            split_at = text.rfind("\n", 0, max_len)
            if split_at == -1:
                split_at = max_len
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip()
        if text:
            chunks.append(text)
        return chunks

    # ── Command ───────────────────────────────────────────────────────────────

    @app_commands.command(name="websearch", description="Search the web — get an AI-synthesized answer with source links")
    @app_commands.describe(
        query="What do you want to search for?",
        max_results="Number of sources to analyse (3–10, default 7)",
        region="Region code, e.g. us-en, uk-en, in-en, wt-wt (global)",
        safesearch="Safe-search filter",
    )
    @app_commands.choices(safesearch=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Moderate (default)", value="moderate"),
        app_commands.Choice(name="Strict", value="strict"),
    ])
    @command_animation
    async def websearch(
        self,
        interaction: discord.Interaction,
        query: str,
        max_results: int = 7,
        region: str = "wt-wt",
        safesearch: str = "moderate",
    ):
        if DDGS is None:
            await self._respond(interaction, discord.Embed(
                title="❌ Search Unavailable",
                description="The `duckduckgo-search` library is not installed.",
                color=discord.Color.red(),
            ), ephemeral=True)
            return

        max_results = max(3, min(10, max_results))
        loop = asyncio.get_event_loop()

        # ── 1. Fetch DDG results ───────────────────────────────────────────
        results = await loop.run_in_executor(
            None, lambda: self._run_ddg(query, max_results, region, safesearch)
        )

        if not results:
            await self._respond(interaction, discord.Embed(
                title="🔍 No Results Found",
                description=f"Nothing came up for **{discord.utils.escape_markdown(query)}**.\nTry different keywords.",
                color=discord.Color.orange(),
            ), ephemeral=True)
            return

        # ── 2. AI synthesis ───────────────────────────────────────────────
        ai_answer = None
        if make_request:
            try:
                messages = self._build_ai_prompt(query, results)
                raw = await make_request(messages, max_tokens=700, include_sheet_data=False)
                if raw and raw.strip():
                    ai_answer = raw.strip()
            except Exception as e:
                logger.warning(f"[WebSearch] AI synthesis failed: {e}")

        # ── 3. Build answer embed ─────────────────────────────────────────
        answer_embed = discord.Embed(
            title=f"🔍 {discord.utils.escape_markdown(query)}",
            color=0x00D9FF,
        )
        answer_embed.set_author(
            name="Web Search",
            icon_url="https://cdn.discordapp.com/emojis/1079957645556879380.png",
        )

        if ai_answer:
            chunks = self._chunk_text(ai_answer, 1024)
            answer_embed.add_field(name="🤖 AI Summary", value=chunks[0], inline=False)
            for extra in chunks[1:]:
                answer_embed.add_field(name="\u200b", value=extra, inline=False)
        else:
            # Fallback: show top-3 snippets if AI unavailable
            answer_embed.description = "*AI synthesis unavailable — showing top snippets.*"
            for i, r in enumerate(results[:3], 1):
                title = (r.get("title") or "Result")[:80]
                body = (r.get("body") or r.get("snippet") or "No description.")[:300]
                href = r.get("href") or r.get("url") or ""
                val = f"{body}\n[🔗 Link]({href})" if href else body
                answer_embed.add_field(name=f"{i}. {title}", value=val, inline=False)

        answer_embed.set_footer(
            text=f"🌐 {len(results)} sources • Region: {region} • Safe: {safesearch.capitalize()}"
        )
        answer_embed.timestamp = discord.utils.utcnow()

        # ── 4. Build paginated sources embed ──────────────────────────────
        view = SearchResultsView(results, query, per_page=5)
        sources_embed = view._build_embed()

        # ── 5. Send ───────────────────────────────────────────────────────
        if interaction.response.is_done():
            await interaction.followup.send(embeds=[answer_embed, sources_embed], view=view)
        else:
            await interaction.response.send_message(embeds=[answer_embed, sources_embed], view=view)

    # ── Utils ─────────────────────────────────────────────────────────────────

    @staticmethod
    async def _respond(interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool = False):
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)


async def setup(bot: commands.Bot):
    await bot.add_cog(WebSearch(bot))
