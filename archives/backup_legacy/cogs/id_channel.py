import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta
import os

from db.mongo_adapters import mongo_enabled, AllianceMembersAdapter
from admin_utils import format_furnace_level

SECRET = "tB87#kPtkxqOS2"

class IDChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_database()
        self.log_directory = 'log'
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)

    def setup_database(self):
        """Initialize ID channel database"""
        if not os.path.exists('db'):
            os.makedirs('db')

        conn = sqlite3.connect('db/id_channel.sqlite')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS id_channels
                     (guild_id INTEGER,
                      alliance_id INTEGER,
                      channel_id INTEGER,
                      created_at TEXT,
                      created_by INTEGER,
                      UNIQUE(guild_id, channel_id))''')
        conn.commit()
        conn.close()

    def _log_debug(self, message):
        """Log debug messages"""
        try:
            with open('debug_id_channel.log', 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            print(message)

    def _upsert_member_from_api(self, fid: int, nickname: str, furnace_lv: int, kid, stove_lv_content, alliance_id: int, avatar_image=None) -> bool:
        """Save member data to database"""
        try:
            member_doc = {
                'fid': str(fid),
                'nickname': nickname,
                'furnace_lv': int(furnace_lv) if furnace_lv is not None else 0,
                'stove_lv': int(furnace_lv) if furnace_lv is not None else 0,
                'stove_lv_content': stove_lv_content,
                'kid': kid,
                'alliance': int(alliance_id),
                'alliance_id': int(alliance_id),
                'avatar_image': avatar_image,
            }

            self._log_debug(f"_upsert_member_from_api called for {fid}. Mongo Enabled: {mongo_enabled()}")

            # Try MongoDB first
            try:
                if mongo_enabled() and AllianceMembersAdapter is not None:
                    self._log_debug(f"Attempting Mongo upsert for {fid}...")
                    result = AllianceMembersAdapter.upsert_member(str(fid), member_doc)
                    self._log_debug(f"Mongo upsert result: {result}")
                    if result:
                        return True
            except Exception as e:
                self._log_debug(f"Mongo upsert exception: {e}")

            # Fallback to SQLite
            try:
                with sqlite3.connect('db/users.sqlite') as users_db:
                    cursor = users_db.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            fid TEXT PRIMARY KEY,
                            nickname TEXT,
                            furnace_lv INTEGER,
                            stove_lv_content TEXT,
                            kid TEXT,
                            alliance INTEGER,
                            avatar_image TEXT
                        )
                    """)
                    cursor.execute("""
                        INSERT OR REPLACE INTO users
                        (fid, nickname, furnace_lv, stove_lv_content, kid, alliance, avatar_image)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(fid),
                        nickname,
                        furnace_lv,
                        stove_lv_content,
                        kid,
                        alliance_id,
                        avatar_image
                    ))
                    users_db.commit()
                    self._log_debug(f"SQLite upsert committed successfully.")
                    return True
            except Exception as e:
                self._log_debug(f"Failed to save member {fid}: {e}")
                return False

        except Exception as e:
            self._log_debug(f"Error in _upsert_member_from_api: {e}")
            return False

    async def process_fid(self, message: discord.Message, fid: int, alliance_id: int):
        """Process a FID from an ID channel"""
        try:
            # Check if already processed (has bot reaction)
            for reaction in message.reactions:
                async for user in reaction.users():
                    if user == self.bot.user:
                        return

            # Import LoginHandler
            from cogs.login_handler import LoginHandler
            login_handler = LoginHandler()

            # Fetch player data
            result = await login_handler.fetch_player_data(str(fid))

            if result['status'] == 'success' and result['data']:
                player_data = result['data']
                nickname = player_data.get('nickname', 'Unknown')
                furnace_lv = player_data.get('stove_lv', 0)
                kid = player_data.get('kid', '')
                stove_lv_content = player_data.get('stove_lv_content', '')
                avatar_image = player_data.get('avatar_image', '')

                # Save to database
                success = self._upsert_member_from_api(
                    fid, nickname, furnace_lv, kid,
                    stove_lv_content, alliance_id, avatar_image
                )

                if success:
                    # Add success reaction
                    await message.add_reaction('✅')

                    # Send confirmation
                    level_str = format_furnace_level(furnace_lv)
                    await message.channel.send(
                        f"✅ **{nickname}** registered successfully!\n"
                        f"🆔 FID: `{fid}`\n"
                        f"⚔️ Furnace Level: `{level_str}`",
                        delete_after=10
                    )
                else:
                    await message.add_reaction('❌')
                    await message.channel.send(
                        f"❌ Failed to register FID `{fid}`. Please try again.",
                        delete_after=10
                    )
            else:
                await message.add_reaction('❌')
                await message.channel.send(
                    f"❌ Player with FID `{fid}` not found.",
                    delete_after=10
                )

        except Exception as e:
            print(f"Error processing FID {fid}: {e}")
            import traceback
            traceback.print_exc()
            await message.add_reaction('❌')
            await message.channel.send(
                "❌ An error occurred during the process.",
                delete_after=10
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for FIDs in ID channels"""
        try:
            # Ignore bot messages and DMs
            if message.author.bot or not message.guild:
                return

            # Check if message content is a 9-digit FID
            content = message.content.strip()
            if not content.isdigit() or len(content) != 9:
                return

            fid = int(content)

            # Get ID channels from database
            with sqlite3.connect('db/id_channel.sqlite') as db:
                cursor = db.cursor()
                cursor.execute(
                    "SELECT channel_id, alliance_id FROM id_channels WHERE guild_id = ?",
                    (message.guild.id)
                )
                channels = cursor.fetchall()

            # Check if message is in an ID channel
            for channel_id, alliance_id in channels:
                if message.channel.id == channel_id:
                    self._log_debug(f"Processing FID {fid} in ID channel {channel_id} for alliance {alliance_id}")
                    # Process the FID
                    await self.process_fid(message, fid, alliance_id)
                    return

        except Exception as e:
            print(f"Error in on_message: {e}")
            import traceback
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_ready(self):
        """Process old messages on bot startup"""
        try:
            with sqlite3.connect('db/id_channel.sqlite') as db:
                cursor = db.cursor()
                cursor.execute("SELECT channel_id, alliance_id FROM id_channels")
                channels = cursor.fetchall()

            invalid_channels = []
            for channel_id, alliance_id in channels:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    invalid_channels.append(channel_id)
                    continue

                # Process messages from last 24 hours
                async for message in channel.history(limit=None, after=datetime.utcnow() - timedelta(days=1)):
                    if message.author.bot:
                        continue

                    # Check if already processed
                    has_bot_reaction = False
                    for reaction in message.reactions:
                        async for user in reaction.users():
                            if user == self.bot.user:
                                has_bot_reaction = True
                                break
                        if has_bot_reaction:
                            break

                    if has_bot_reaction:
                        continue

                    content = message.content.strip()
                    if not content or not content.isdigit() or len(content) != 9:
                        continue

                    fid = int(content)
                    await self.process_fid(message, fid, alliance_id)

            # Clean up invalid channels
            if invalid_channels:
                with sqlite3.connect('db/id_channel.sqlite') as db:
                    cursor = db.cursor()
                    placeholders = ','.join('?' * len(invalid_channels))
                    cursor.execute(f"""
                        DELETE FROM id_channels
                        WHERE channel_id IN ({placeholders})
                    """, invalid_channels)
                    db.commit()

        except Exception as e:
            print(f"Error in on_ready: {e}")

def setup(bot):
    bot.add_cog(IDChannel(bot))
