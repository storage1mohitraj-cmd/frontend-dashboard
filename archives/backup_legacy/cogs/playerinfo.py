from typing import Optional
"""/playerinfo cog - single clean implementation with logging.
"""

import re
import time
import hashlib
import aiohttp
import ssl
import asyncio
import sqlite3
from datetime import datetime
import os
import logging
import discord
import urllib.parse
from discord.ext import commands
from thinking_animation import ThinkingAnimation
from command_animator import command_animation

# Player API endpoint and secret
API_URL = "https://wos-giftcode-api.centurygame.com/api/player"
SECRET = "tB87#kPtkxqOS2"

try:
    _env_dev_gid = os.getenv('DEV_GUILD_ID')
    DEV_GUILD_ID = int(_env_dev_gid) if _env_dev_gid else 850787279664185434
except Exception:
    DEV_GUILD_ID = 850787279664185434

WATERMARK_URL = "https://cdn.discordapp.com/attachments/1435569370389807144/1436437186424606741/unnamed_4.png?ex=690f99e0&is=690e4860&hm=2262bc4ceea28787c91c5bfcb2d6e7fac28cda152c4963a9b4375eac4913b063"


def map_furnace(lv: int) -> Optional[str ]:
    if lv is None:
        return None
    try:
        lv = int(lv)
    except Exception:
        return None

    if 31 <= lv <= 39:
        return "FC1"
    if lv >= 40:
        fc_index = ((lv - 40) // 5) + 2
        return f"FC{fc_index}"
    return None


class PlayerInfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('bot.playerinfo')
        self._sem = asyncio.Semaphore(6)
        self._thinking_animation = ThinkingAnimation()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if message.author.bot:
                return

            content = (message.content or "")
            if content.strip().startswith(('!Add', '!Remove')):
                return

            m = re.search(r"\b(\d{9})\b", content)
            if not m:
                return

            fid = m.group(1)
            await self.handle_fid_message(message, fid)
        except Exception as outer_e:
            self.logger.exception("Unexpected error in playerinfo on_message: %s", outer_e)

    async def handle_fid_message(self, message: discord.Message, fid: str):
        try:
            if getattr(message, '_playerinfo_handled', False):
                return
            try:
                message._playerinfo_handled = True
            except Exception:
                pass

            channel_type = 'DM' if isinstance(message.channel, discord.DMChannel) else f'GUILD:{getattr(message.guild, "id", "unknown")}'
            self.logger.info("playerinfo (message) detected fid=%s from user=%s in %s", fid, getattr(message.author, 'id', 'unknown'), channel_type)

            thinking_msg = None
            try:
                thinking_embed = discord.Embed(
                    title="🤖 Processing...",
                    description=f"```\n{self._thinking_animation.generate_binary_frame(24)}\n```\n*{self._thinking_animation.generate_status_text()}*",
                    color=0x9b59b6
                )
                thinking_embed.set_footer(text="Fetching player information...")
                thinking_embed.set_thumbnail(url="https://i.postimg.cc/fLLWWSKq/ezgif-278f9fa56d75db.gif")
                thinking_msg = await message.reply(embed=thinking_embed, mention_author=False)
            except Exception as e:
                self.logger.debug(f"Failed to show thinking animation: {e}")

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://wos-giftcode-api.centurygame.com",
            }

            async with self._sem:
                current_time = int(time.time() * 1000)
                form = f"fid={fid}&time={current_time}"
                sign = hashlib.md5((form + SECRET).encode("utf-8")).hexdigest()
                payload = f"sign={sign}&{form}"

                try:
                    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                        async with session.post(API_URL, data=payload, headers=headers, timeout=20) as resp:
                            text = await resp.text()
                            try:
                                js = await resp.json()
                            except Exception:
                                self.logger.debug("playerinfo (message) invalid json for fid=%s: %s", fid, text)
                                return
                except Exception as e:
                    self.logger.debug("playerinfo (message) network error for fid=%s: %s", fid, e)
                    return

            if not js or js.get("code") != 0:
                try:
                    if thinking_msg:
                        await thinking_msg.delete()
                    await message.add_reaction("❌")
                except Exception:
                    pass
                return

            data = js.get('data', {})
            nickname = data.get('nickname', 'Unknown')
            kid = data.get('kid', 'N/A')
            stove_lv = data.get('stove_lv')
            stove_icon = data.get('stove_lv_content')
            avatar = data.get('avatar_image')

            try:
                lv_int = int(stove_lv) if stove_lv is not None else None
            except Exception:
                lv_int = None
            fc = map_furnace(lv_int)

            embed = discord.Embed(colour=discord.Colour.blurple())
            try:
                author_name = f"{nickname}"
                if stove_icon:
                    p = urllib.parse.urlparse(stove_icon)
                    if p.scheme in ("http", "https") and p.netloc:
                        embed.set_author(name=author_name, icon_url=stove_icon)
                    else:
                        embed.set_author(name=author_name)
                else:
                    embed.set_author(name=author_name)
            except Exception:
                embed.set_author(name=nickname)

            try:
                if avatar:
                    p2 = urllib.parse.urlparse(avatar)
                    if p2.scheme in ("http", "https") and p2.netloc:
                        embed.set_thumbnail(url=avatar)
            except Exception:
                pass

            if lv_int is None:
                furnace_display = f"```{stove_lv or 'N/A'}```"
            else:
                furnace_display = f"```{fc or lv_int}```"

            pid_display = f"```{fid}```"
            raw_state = str(kid or "N/A")
            if raw_state.startswith("#"):
                state_val = f"```{raw_state}```"
            else:
                state_val = f"```#{raw_state}```"

            embed.add_field(name="🪪 Player ID", value=pid_display, inline=True)
            embed.add_field(name="🏠 STATE", value=state_val, inline=True)
            embed.add_field(name="Furnace Level", value=furnace_display, inline=True)

            try:
                alliance_name = None
                with sqlite3.connect('db/users.sqlite') as users_db:
                    cur = users_db.cursor()
                    cur.execute('SELECT alliance FROM users WHERE fid = ?', (fid,))
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        alliance_val = str(row[0])
                        if alliance_val.isdigit():
                            try:
                                with sqlite3.connect('db/alliance.sqlite') as a_db:
                                    ac = a_db.cursor()
                                    ac.execute('SELECT name FROM alliance_list WHERE alliance_id = ?', (int(alliance_val),))
                                    arow = ac.fetchone()
                                    if arow:
                                        alliance_name = arow[0]
                                    else:
                                        alliance_name = alliance_val
                            except Exception:
                                alliance_name = alliance_val
                        else:
                            alliance_name = alliance_val

                if alliance_name:
                    embed.add_field(name="🏰 Alliance", value=f"```{alliance_name}```", inline=True)
            except Exception:
                pass

            try:
                if WATERMARK_URL:
                    p3 = urllib.parse.urlparse(WATERMARK_URL)
                    if p3.scheme in ("http", "https") and p3.netloc:
                        embed.set_footer(text="Requested via Magnus", icon_url=WATERMARK_URL)
                    else:
                        embed.set_footer(text="Requested via Magnus")
                else:
                    embed.set_footer(text="Requested via Magnus")
            except Exception:
                embed.set_footer(text="Requested via Magnus")

            try:
                if thinking_msg:
                    await thinking_msg.delete()
                await message.reply(embed=embed, mention_author=False)
            except Exception as send_err:
                self.logger.debug("Failed to send playerinfo reply: %s", send_err)
        except Exception as outer_e:
            self.logger.exception("Unexpected error in playerinfo handler: %s", outer_e)

    @discord.slash_command(
        name="playerinfo",
        description="Get player info by 9-digit player id. Accepts comma-separated list (max 30).")
    @command_animation
    async def playerinfo(self, interaction: discord.ApplicationContext, player_id: str):
        user_id = getattr(interaction.user, 'id', 'unknown')
        self.logger.info("/playerinfo invoked by user %s for player_id=%s", user_id, player_id)

        ids = [p.strip() for p in str(player_id).split(',') if p.strip()]
        if not ids:
            await interaction.response.send_message("No player ids provided.", ephemeral=True)
            return
        if len(ids) > 30:
            if interaction.response.is_done():
                await interaction.followup.send("Too many ids — max 30 at a time.", ephemeral=True)
            else:
                await interaction.response.send_message("Too many ids — max 30 at a time.", ephemeral=True)
            return

        invalid = [p for p in ids if not re.fullmatch(r"\d{9}", p)]
        if invalid:
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"The following ids are invalid (must be 9 digits): {', '.join(invalid)}",
                    ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"The following ids are invalid (must be 9 digits): {', '.join(invalid)}",
                    ephemeral=True)
            return

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://wos-giftcode-api.centurygame.com",
        }

        def _is_valid_url(u: str) -> bool:
            if not u:
                return False
            try:
                p = urllib.parse.urlparse(u)
                return p.scheme in ("http", "https") and bool(p.netloc)
            except Exception:
                return False

        sem = asyncio.Semaphore(10)

        async def fetch_one(session: aiohttp.ClientSession, fid: str) -> Optional[tuple[str, dict ]Optional[, Exception ]]:
            async with sem:
                try:
                    current_time = int(time.time() * 1000)
                    form = f"fid={fid}&time={current_time}"
                    sign = hashlib.md5((form + SECRET).encode("utf-8")).hexdigest()
                    payload = f"sign={sign}&{form}"
                    self.logger.debug("playerinfo request for %s time=%s", fid, current_time)
                    async with session.post(API_URL, data=payload, headers=headers, timeout=20) as resp:
                        text = await resp.text()
                        try:
                            js = await resp.json()
                        except Exception:
                            self.logger.warning("Invalid JSON response for fid=%s: %s", fid, text)
                            return fid, None, None
                        return fid, js, None
                except Exception as e:
                    self.logger.exception("Request error for fid=%s", fid)
                    return fid, None, e

        def build_embed_for(fid: str, js: Optional[dict ]) -> discord.Embed:
            embed = discord.Embed(colour=discord.Colour.blurple())
            if js is None:
                embed.description = "No valid response from API."
                embed.set_footer(text="Requested via /playerinfo . Magnus")
                return embed

            if js.get("code") != 0:
                api_msg_raw = js.get('msg') or ''
                api_msg = str(api_msg_raw).lower().replace('_', ' ')
                if ('role' in api_msg and ('not' in api_msg and ('exist' in api_msg or 'found' in api_msg))) \
                   or (('not' in api_msg) and ('exist' in api_msg or 'found' in api_msg)):
                    embed.description = "Player not found — check the 9-digit player ID and try again."
                else:
                    embed.description = f"API error: {api_msg_raw}"
                embed.set_footer(text="Requested via /playerinfo . Magnus")
                return embed

            data = js.get('data', {})
            nickname = data.get('nickname', 'Unknown')
            kid = data.get('kid', 'N/A')
            stove_lv = data.get('stove_lv')
            stove_icon = data.get('stove_lv_content')
            avatar = data.get('avatar_image')

            try:
                lv_int = int(stove_lv) if stove_lv is not None else None
            except Exception:
                lv_int = None
            fc = map_furnace(lv_int)

            embed = discord.Embed(colour=discord.Colour.blurple())
            try:
                author_name = f"{nickname}"
                if stove_icon and _is_valid_url(stove_icon):
                    embed.set_author(name=author_name, icon_url=stove_icon)
                else:
                    embed.set_author(name=author_name)
            except Exception:
                embed.set_author(name=author_name)

            if avatar and _is_valid_url(avatar):
                try:
                    embed.set_thumbnail(url=avatar)
                except Exception:
                    pass

            if lv_int is None:
                furnace_display = f"```{stove_lv or 'N/A'}```"
            else:
                furnace_display = f"```{fc or lv_int}```"

            pid_display = f"```{fid}```"
            raw_state = str(kid or "N/A")
            if raw_state.startswith("#"):
                state_val = f"```{raw_state}```"
            else:
                state_val = f"```#{raw_state}```"

            embed.add_field(name="🪪 Player ID", value=pid_display, inline=True)
            embed.add_field(name="🏠 STATE", value=state_val, inline=True)
            embed.add_field(name="Furnace Level", value=furnace_display, inline=True)

            try:
                if WATERMARK_URL and _is_valid_url(WATERMARK_URL):
                    embed.set_footer(text="Requested via /playerinfo . Magnus", icon_url=WATERMARK_URL)
                else:
                    embed.set_footer(text="Requested via /playerinfo . Magnus")
            except Exception:
                embed.set_footer(text="Requested via /playerinfo . Magnus")

            return embed

        results = []
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                tasks = [asyncio.create_task(fetch_one(session, fid)) for fid in ids]
                for coro in asyncio.as_completed(tasks):
                    fid, js, exc = await coro
                    if exc:
                        self.logger.warning("Network error for fid=%s: %s", fid, exc)
                        embed = discord.Embed(colour=discord.Colour.blurple(), description=f"Request error: {exc}")
                        embed.set_footer(text="Requested via /playerinfo . Magnus")
                        await interaction.followup.send(embed=embed)
                        continue
                    embed = build_embed_for(fid, js)
                    await interaction.followup.send(embed=embed)
        except Exception as e:
            self.logger.exception("Unexpected error during batch fetch")
            if interaction.response.is_done():
                await interaction.followup.send(f"Unexpected error: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Unexpected error: {e}", ephemeral=True)
            return

    @discord.slash_command(
        name="editplayerinfo",
        description="Update an existing playerinfo message with new player data.")
    async def editplayerinfo(self, interaction: discord.ApplicationContext, message_id: str, player_id: str):
        user_id = getattr(interaction.user, 'id', 'unknown')
        self.logger.info("/editplayerinfo invoked by user %s for msg=%s player_id=%s", user_id, message_id, player_id)

        if not re.fullmatch(r"\d{9}", player_id):
            await interaction.response.send_message("Invalid player ID. Must be 9 digits.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            m_id = int(message_id)
            msg = await interaction.channel.fetch_message(m_id)
        except discord.NotFound:
            await interaction.followup.send("Message not found in this channel.", ephemeral=True)
            return
        except (ValueError, discord.HTTPException) as e:
            await interaction.followup.send(f"Error fetching message: {e}", ephemeral=True)
            return

        if msg.author.id != self.bot.user.id:
            await interaction.followup.send("I can only edit my own messages.", ephemeral=True)
            return

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://wos-giftcode-api.centurygame.com",
        }

        js = None
        try:
            current_time = int(time.time() * 1000)
            form = f"fid={player_id}&time={current_time}"
            sign = hashlib.md5((form + SECRET).encode("utf-8")).hexdigest()
            payload = f"sign={sign}&{form}"

            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                async with session.post(API_URL, data=payload, headers=headers, timeout=20) as resp:
                    text = await resp.text()
                    try:
                        js = await resp.json()
                    except Exception:
                        self.logger.warning("Invalid JSON response for fid=%s: %s", player_id, text)
        except Exception as e:
            self.logger.exception("Request error for fid=%s", player_id)
            await interaction.followup.send(f"Network error fetching player info: {e}", ephemeral=True)
            return

        def _is_valid_url(u: str) -> bool:
            if not u:
                return False
            try:
                p = urllib.parse.urlparse(u)
                return p.scheme in ("http", "https") and bool(p.netloc)
            except Exception:
                return False

        embed = discord.Embed(colour=discord.Colour.blurple())

        if js is None:
            embed.description = "No valid response from API."
            embed.set_footer(text="Requested via /editplayerinfo . Magnus")
        elif js.get("code") != 0:
            api_msg_raw = js.get('msg') or ''
            api_msg = str(api_msg_raw).lower().replace('_', ' ')
            if ('role' in api_msg and ('not' in api_msg and ('exist' in api_msg or 'found' in api_msg))) \
               or (('not' in api_msg) and ('exist' in api_msg or 'found' in api_msg)):
                embed.description = "Player not found — check the 9-digit player ID and try again."
            else:
                embed.description = f"API error: {api_msg_raw}"
            embed.set_footer(text="Requested via /editplayerinfo . Magnus")
        else:
            data = js.get('data', {})
            nickname = data.get('nickname', 'Unknown')
            kid = data.get('kid', 'N/A')
            stove_lv = data.get('stove_lv')
            stove_icon = data.get('stove_lv_content')
            avatar = data.get('avatar_image')

            try:
                lv_int = int(stove_lv) if stove_lv is not None else None
            except Exception:
                lv_int = None
            fc = map_furnace(lv_int)

            try:
                author_name = f"{nickname}"
                if stove_icon and _is_valid_url(stove_icon):
                    embed.set_author(name=author_name, icon_url=stove_icon)
                else:
                    embed.set_author(name=author_name)
            except Exception:
                embed.set_author(name=author_name)

            if avatar and _is_valid_url(avatar):
                try:
                    embed.set_thumbnail(url=avatar)
                except Exception:
                    pass

            if lv_int is None:
                furnace_display = f"```{stove_lv or 'N/A'}```"
            else:
                furnace_display = f"```{fc or lv_int}```"

            pid_display = f"```{player_id}```"
            raw_state = str(kid or "N/A")
            if raw_state.startswith("#"):
                state_val = f"```{raw_state}```"
            else:
                state_val = f"```#{raw_state}```"

            embed.add_field(name="🪪 Player ID", value=pid_display, inline=True)
            embed.add_field(name="🏠 STATE", value=state_val, inline=True)
            embed.add_field(name="Furnace Level", value=furnace_display, inline=True)

            try:
                alliance_name = None
                with sqlite3.connect('db/users.sqlite') as users_db:
                    cur = users_db.cursor()
                    cur.execute('SELECT alliance FROM users WHERE fid = ?', (player_id,))
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        alliance_val = str(row[0])
                        if alliance_val.isdigit():
                            try:
                                with sqlite3.connect('db/alliance.sqlite') as a_db:
                                    ac = a_db.cursor()
                                    ac.execute('SELECT name FROM alliance_list WHERE alliance_id = ?', (int(alliance_val),))
                                    arow = ac.fetchone()
                                    if arow:
                                        alliance_name = arow[0]
                                    else:
                                        alliance_name = alliance_val
                            except Exception:
                                alliance_name = alliance_val
                        else:
                            alliance_name = alliance_val

                if alliance_name:
                    embed.add_field(name="🏰 Alliance", value=f"```{alliance_name}```", inline=True)
            except Exception:
                pass

            try:
                if WATERMARK_URL and _is_valid_url(WATERMARK_URL):
                    embed.set_footer(text="Requested via /editplayerinfo . Magnus", icon_url=WATERMARK_URL)
                else:
                    embed.set_footer(text="Requested via /editplayerinfo . Magnus")
            except Exception:
                embed.set_footer(text="Requested via /editplayerinfo . Magnus")

        try:
            await msg.edit(embed=embed)
            await interaction.followup.send(f"Updated message {message_id}.", ephemeral=True)
        except Exception as e:
            self.logger.error("Failed to edit message %s: %s", message_id, e)
            await interaction.followup.send(f"Failed to edit message: {e}", ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(PlayerInfoCog(bot))
