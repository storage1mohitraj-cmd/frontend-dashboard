import discord
from discord.ext import commands
import aiohttp
import hashlib
import ssl
import time
import asyncio
import sqlite3
from admin_utils import format_furnace_level

async def fid_autocomplete(ctx: discord.AutocompleteContext):
    current = ctx.value
    try:
        with sqlite3.connect('db/users.sqlite') as users_db:
            cursor = users_db.cursor()
            cursor.execute("SELECT fid, nickname FROM users")
            users = cursor.fetchall()
        
        choices = [
            discord.OptionChoice(name=f"{nickname} ({fid})", value=str(fid))
            for fid, nickname in users
        ]
        
        if current:
            filtered_choices = [choice for choice in choices if current.lower() in choice.name.lower()][:25]
        else:
            filtered_choices = choices[:25]
            
        return filtered_choices
    except Exception as e:
        print(f"Autocomplete could not be loaded: {e}")
        return []

class WCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('db/changes.sqlite')
        self.c = self.conn.cursor()
        self.SECRET = "tB87#kPtkxqOS2"

        self.level_mapping = type('obj', (object,), {'get': lambda self, k, d=None: format_furnace_level(k)})()

    def cog_unload(self):
        if hasattr(self, 'conn'):
            self.conn.close()

    @discord.slash_command(name='w', description='Fetches user info using fid.')
    async def w(
        self, 
        interaction: discord.ApplicationContext, 
        fid: str = discord.Option(str, "User FID", autocomplete=fid_autocomplete)
    ):
        await self.fetch_user_info(interaction, fid)


    async def fetch_user_info(self, interaction: discord.ApplicationContext, fid: str):
        try:
            await interaction.response.defer(thinking=True)

            current_time = int(time.time() * 1000)
            form = f"fid={fid}&time={current_time}"
            sign = hashlib.md5((form + self.SECRET).encode('utf-8')).hexdigest()
            form = f"sign={sign}&{form}"

            url = 'https://wos-giftcode-api.centurygame.com/api/player'
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            max_retries = 3
            retry_delay = 60

            for attempt in range(max_retries):
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, data=form, ssl=ssl_context) as response:
                        if response.status == 200:
                            data = await response.json()
                            nickname = data['data']['nickname']
                            fid_value = data['data']['fid']
                            stove_level = data['data']['stove_lv']
                            kid = data['data']['kid']
                            avatar_image = data['data']['avatar_image']
                            stove_lv_content = data['data'].get('stove_lv_content')

                            if stove_level > 30:
                                stove_level_name = self.level_mapping.get(stove_level, f"Level {stove_level}")
                            else:
                                stove_level_name = f"Level {stove_level}"

                            user_info = None
                            alliance_info = None

                            with sqlite3.connect('db/users.sqlite') as users_db:
                                cursor = users_db.cursor()
                                cursor.execute("SELECT *, alliance FROM users WHERE fid=?", (fid_value,))
                                user_info = cursor.fetchone()

                                if user_info and user_info[-1]:
                                    with sqlite3.connect('db/alliance.sqlite') as alliance_db:
                                        cursor = alliance_db.cursor()
                                        cursor.execute("SELECT name FROM alliance_list WHERE alliance_id=?", (user_info[-1],))
                                        alliance_info = cursor.fetchone()

                            embed = discord.Embed(
                                title=f"👤 {nickname}",
                                description=(
                                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"**🆔 FID:** `{fid_value}`\n"
                                    f"**🔥 Furnace Level:** `{stove_level_name}`\n"
                                    f"**🌍 State:** `{kid}`\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                                ),
                                color=discord.Color.blue()
                            )

                            if alliance_info:
                                embed.description += f"**🏰 Alliance:** `{alliance_info[0]}`\n━━━━━━━━━━━━━━━━━━━━━━\n"

                            registration_status = "Registered on the List ✅" if user_info else "Not on the List ❌"
                            embed.set_footer(text=registration_status)

                            if avatar_image:
                                embed.set_image(url=avatar_image)
                            if isinstance(stove_lv_content, str) and stove_lv_content.startswith("http"):
                                embed.set_thumbnail(url=stove_lv_content)

                            await interaction.followup.send(embed=embed)
                            return

                        elif response.status == 429:
                            if attempt < max_retries - 1:
                                await interaction.followup.send("API limit reached, your result will be displayed automatically shortly...")
                                await asyncio.sleep(retry_delay)
            await interaction.followup.send(f"User with ID {fid} not found or an error occurred after multiple attempts.")

        except Exception as e:
            print(f"An error occurred: {e}")
            await interaction.followup.send("An error occurred while fetching user info.")


def setup(bot):
    bot.add_cog(WCommand(bot))
