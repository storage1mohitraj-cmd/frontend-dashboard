import discord
from discord import app_commands
from discord.ext import commands
import sqlite3  
import asyncio
from datetime import datetime
from discord.ext import tasks
from typing import List, Dict, Optional
import os
from .login_handler import LoginHandler
from command_animator import command_animation
try:
    from db.mongo_adapters import mongo_enabled, AdminsAdapter, AlliancesAdapter, AllianceSettingsAdapter, AllianceMembersAdapter, FurnaceHistoryAdapter, AllianceMonitoringAdapter
except Exception as import_error:
    # Fallback: If MongoDB adapters fail to import, use SQLite exclusively
    print(f"[WARNING] MongoDB adapters import failed: {import_error}. Using SQLite fallback.")
    mongo_enabled = lambda: False
    
    # Provide dummy adapter classes that always return None/False
    class AdminsAdapter:
        @staticmethod
        def get(user_id): return None
        @staticmethod
        def upsert(user_id, is_initial): return False
        @staticmethod
        def count(): return 0
    
    class AlliancesAdapter:
        @staticmethod
        def get_all(): return []
        @staticmethod
        async def get_all_async(): return []
        @staticmethod
        def get(alliance_id): return None
    
    class AllianceSettingsAdapter:
        @staticmethod
        def get(alliance_id): return None
    
    class AllianceMembersAdapter:
        @staticmethod
        def get_all_members(): return []
        @staticmethod
        async def get_all_members_async(): return []
        @staticmethod
        def get_member(fid): return None
        @staticmethod
        async def get_member_async(fid): return None
        @staticmethod
        def upsert_member(fid, data): return False
        @staticmethod
        async def upsert_member_async(fid, data): return False

    class AllianceMonitoringAdapter:
        @staticmethod
        def get_all_monitors(): return []
        @staticmethod
        async def get_all_monitors_async(): return []

    class FurnaceHistoryAdapter:
        @staticmethod
        def insert(data): return False
        @staticmethod
        async def insert_async(data): return False


# Import database utilities for consistent path handling
try:
    from db_utils import get_db_connection
except ImportError:
    # Fallback if db_utils is not available
    from pathlib import Path
    def get_db_connection(db_name: str, **kwargs):
        repo_root = Path(__file__).resolve().parents[1]
        db_dir = repo_root / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(db_dir / db_name), **kwargs)

class Alliance(commands.Cog):
    def __init__(self, bot, conn):
        self.bot = bot
        self.conn = conn
        self.c = self.conn.cursor()
        
        # Use centralized database connection utility for consistent paths
        self.conn_users = get_db_connection('users.sqlite')
        self.c_users = self.conn_users.cursor()
        
        self.conn_settings = get_db_connection('settings.sqlite')
        self.c_settings = self.conn_settings.cursor()
        
        self.conn_giftcode = get_db_connection('giftcode.sqlite')
        self.c_giftcode = self.conn_giftcode.cursor()

        self._create_table()
        self._check_and_add_column()

        # Alliance Monitoring Initialization
        self.login_handler = LoginHandler()
        
        # Check API availability and enable dual-API mode if both are available
        # This will be called asynchronously when the monitoring task starts
        self._api_check_done = False
        
        # Level mapping for furnace levels
        self.level_mapping = {
            31: "30-1", 32: "30-2", 33: "30-3", 34: "30-4",
            35: "FC 1", 36: "FC 1-1", 37: "FC 1-2", 38: "FC 1-3", 39: "FC 1-4",
            40: "FC 2", 41: "FC 2-1", 42: "FC 2-2", 43: "FC 2-3", 44: "FC 2-4",
            45: "FC 3", 46: "FC 3-1", 47: "FC 3-2", 48: "FC 3-3", 49: "FC 3-4",
            50: "FC 4", 51: "FC 4-1", 52: "FC 4-2", 53: "FC 4-3", 54: "FC 4-4",
            55: "FC 5", 56: "FC 5-1", 57: "FC 5-2", 58: "FC 5-3", 59: "FC 5-4",
            60: "FC 6", 61: "FC 6-1", 62: "FC 6-2", 63: "FC 6-3", 64: "FC 6-4",
            65: "FC 7", 66: "FC 7-1", 67: "FC 7-2", 68: "FC 7-3", 69: "FC 7-4",
            70: "FC 8", 71: "FC 8-1", 72: "FC 8-2", 73: "FC 8-3", 74: "FC 8-4",
            75: "FC 9", 76: "FC 9-1", 77: "FC 9-2", 78: "FC 9-3", 79: "FC 9-4",
            80: "FC 10", 81: "FC 10-1", 82: "FC 10-2", 83: "FC 10-3", 84: "FC 10-4"
        }
        
        # Furnace level emojis
        # Furnace level emojis - REMOVED as per request
        # self.fl_emojis = { ... }
        
        # Logging
        self.log_directory = 'log'
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)
        self.log_file = os.path.join(self.log_directory, 'alliance_monitoring.txt')
        
        # Initialize monitoring tables
        self._initialize_monitoring_tables()
        
        # Sync from MongoDB if enabled
        self._sync_from_mongo()
        
        # Start background monitoring task
        self.monitor_alliances.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.monitor_alliances.cancel()

    def _create_table(self):
        # Core alliance list
        self.c.execute("""
            CREATE TABLE IF NOT EXISTS alliance_list (
                alliance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                discord_server_id INTEGER
            )
        """)

        # Settings for alliances (may be stored in SQLite for legacy/partial flows)
        try:
            self.c.execute("""
                CREATE TABLE IF NOT EXISTS alliancesettings (
                    alliance_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    interval INTEGER DEFAULT 0
                )
            """)
        except Exception:
            # Best-effort: if creating this table fails, other code will handle exceptions
            pass

        # Ensure legacy/local DB tables used elsewhere exist (best-effort).
        try:
            # giftcode DB tables
            self.c_giftcode.execute("""
                CREATE TABLE IF NOT EXISTS giftcodecontrol (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alliance_id INTEGER,
                    status INTEGER
                )
            """)

            self.c_giftcode.execute("""
                CREATE TABLE IF NOT EXISTS giftcode_channel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alliance_id INTEGER,
                    channel_id INTEGER
                )
            """)
        except Exception:
            pass

        try:
            # users table (minimal shape to allow counts/queries)
            self.c_users.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fid TEXT,
                    nickname TEXT,
                    furnace_lv INTEGER DEFAULT 0,
                    kid INTEGER,
                    stove_lv_content TEXT,
                    alliance INTEGER
                )
            """)
        except Exception:
            pass

        try:
            # settings DB: admin + adminserver used by settings flow
            self.c_settings.execute("""
                CREATE TABLE IF NOT EXISTS admin (
                    id INTEGER PRIMARY KEY,
                    is_initial INTEGER DEFAULT 0
                )
            """)
            self.c_settings.execute("""
                CREATE TABLE IF NOT EXISTS adminserver (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alliances_id INTEGER
                )
            """)
            # Server lock table - for locking bot on specific servers
            self.c_settings.execute("""
                CREATE TABLE IF NOT EXISTS server_locks (
                    guild_id INTEGER PRIMARY KEY,
                    locked INTEGER DEFAULT 0,
                    locked_by INTEGER,
                    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        except Exception:
            pass

        # Commit all changes where possible
        try:
            self.conn.commit()
        except Exception:
            pass
        try:
            self.conn_giftcode.commit()
        except Exception:
            pass
        try:
            self.conn_users.commit()
        except Exception:
            pass
        try:
            self.conn_settings.commit()
        except Exception:
            pass

    def _check_and_add_column(self):
        self.c.execute("PRAGMA table_info(alliance_list)")
        columns = [info[1] for info in self.c.fetchall()]
        if "discord_server_id" not in columns:
            self.c.execute("ALTER TABLE alliance_list ADD COLUMN discord_server_id INTEGER")
            self.conn.commit()

    def _get_admin(self, user_id):
        """Get admin info with MongoDB fallback to SQLite"""
        try:
            if mongo_enabled():
                admin = AdminsAdapter.get(user_id)
                if admin is not None:
                    return admin
                # If MongoDB returns None, fall back to SQLite
        except Exception as e:
            print(f"[WARNING] MongoDB AdminsAdapter.get failed: {e}. Falling back to SQLite.")
        
        # SQLite fallback
        try:
            self.c_settings.execute("SELECT id, is_initial FROM admin WHERE id = ?", (user_id,))
            return self.c_settings.fetchone()
        except Exception as e:
            print(f"[ERROR] SQLite admin query failed: {e}")
            return None

    def _upsert_admin(self, user_id, is_initial=1):
        """Insert/update admin with MongoDB fallback to SQLite"""
        success = False
        try:
            if mongo_enabled():
                success = AdminsAdapter.upsert(user_id, is_initial)
                if success:
                    return True
                # If MongoDB fails, fall back to SQLite
                print(f"[WARNING] MongoDB AdminsAdapter.upsert returned False. Falling back to SQLite.")
        except Exception as e:
            print(f"[WARNING] MongoDB AdminsAdapter.upsert failed: {e}. Falling back to SQLite.")
        
        # SQLite fallback
        try:
            self.c_settings.execute(
                "INSERT OR REPLACE INTO admin (id, is_initial) VALUES (?, ?)",
                (user_id, is_initial)
            )
            self.conn_settings.commit()
            return True
        except Exception as e:
            print(f"[ERROR] SQLite admin upsert failed: {e}")
            return False

    def _count_admins(self):
        """Count admins with MongoDB fallback to SQLite"""
        try:
            if mongo_enabled():
                count = AdminsAdapter.count()
                if count is not None and count >= 0:
                    return count
                # If MongoDB returns None, fall back to SQLite
        except Exception as e:
            print(f"[WARNING] MongoDB AdminsAdapter.count failed: {e}. Falling back to SQLite.")
        
        # SQLite fallback
        try:
            self.c_settings.execute("SELECT COUNT(*) FROM admin")
            return self.c_settings.fetchone()[0]
        except Exception as e:
            print(f"[ERROR] SQLite admin count failed: {e}")
            return 0


    async def view_alliances(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        if interaction.guild is None:
            await interaction.followup.send("❌ This command must be used in a server, not in DMs.", ephemeral=True)
            return

        user_id = interaction.user.id
        if mongo_enabled():
            admin = AdminsAdapter.get(user_id)
        else:
            self.c_settings.execute("SELECT id, is_initial FROM admin WHERE id = ?", (user_id,))
            admin = self.c_settings.fetchone()

        if admin is None:
            await interaction.followup.send("You do not have permission to view alliances.", ephemeral=True)
            return

        is_initial = admin[1] if isinstance(admin, tuple) else int(admin.get('is_initial', 0))
        guild_id = interaction.guild.id

        try:
            if mongo_enabled():
                docs = AlliancesAdapter.get_all()
                if is_initial == 1:
                    alliances = [(d['alliance_id'], d['name'], (AllianceSettingsAdapter.get(d['alliance_id']) or {}).get('interval', 0)) for d in docs]
                else:
                    alliances = [(d['alliance_id'], d['name'], (AllianceSettingsAdapter.get(d['alliance_id']) or {}).get('interval', 0)) for d in docs if int(d.get('discord_server_id') or 0) == guild_id]
            else:
                if is_initial == 1:
                    query = """
                        SELECT a.alliance_id, a.name, COALESCE(s.interval, 0) as interval
                        FROM alliance_list a
                        LEFT JOIN alliancesettings s ON a.alliance_id = s.alliance_id
                        ORDER BY a.alliance_id ASC
                    """
                    self.c.execute(query)
                else:
                    query = """
                        SELECT a.alliance_id, a.name, COALESCE(s.interval, 0) as interval
                        FROM alliance_list a
                        LEFT JOIN alliancesettings s ON a.alliance_id = s.alliance_id
                        WHERE a.discord_server_id = ?
                        ORDER BY a.alliance_id ASC
                    """
                    self.c.execute(query, (guild_id,))
                alliances = self.c.fetchall()

            alliance_list = ""
            for alliance_id, name, interval in alliances:
                
                if mongo_enabled():
                    try:
                        members = AllianceMembersAdapter.get_all_members()
                        member_count = sum(1 for m in members if int(m.get('alliance', 0)) == alliance_id)
                    except Exception:
                        member_count = 0
                else:
                    self.c_users.execute("SELECT COUNT(*) FROM users WHERE alliance = ?", (alliance_id,))
                    member_count = self.c_users.fetchone()[0]
                
                interval_text = f"{interval} minutes" if interval > 0 else "No automatic control"
                alliance_list += f"🛡️ **{alliance_id}: {name}**\n👥 Members: {member_count}\n⏱️ Control Interval: {interval_text}\n\n"

            if not alliance_list:
                alliance_list = "No alliances found."

            embed = discord.Embed(
                title="🛡️ Alliance Directory",
                description=alliance_list,
                color=0x06B6D4
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                "An error occurred while fetching alliances.", 
                ephemeral=True
            )

    async def alliance_autocomplete(self, interaction: discord.Interaction, current: str):
        self.c.execute("SELECT alliance_id, name FROM alliance_list")
        alliances = self.c.fetchall()
        return [
            app_commands.Choice(name=f"{name} (ID: {alliance_id})", value=str(alliance_id))
            for alliance_id, name in alliances if current.lower() in name.lower()
        ][:25]

    async def show_main_menu(self, interaction: discord.Interaction):
        """Programmatic access to settings menu"""
        await self.settings.callback(self, interaction)

    @app_commands.command(name="settings", description="Open settings menu.")
    @command_animation
    async def settings(self, interaction: discord.Interaction):
        try:
            if interaction.guild is not None: # Check bot permissions only if in a guild
                perm_check = interaction.guild.get_member(interaction.client.user.id)
                if not perm_check.guild_permissions.administrator:
                    await interaction.response.send_message(
                        "Beeb boop 🤖 I need **Administrator** permissions to function. "
                        "Go to server settings --> Roles --> find my role --> scroll down and turn on Administrator", 
                        ephemeral=True
                    )
                    return
                
            # Use helper method with automatic fallback
            admin_count = self._count_admins()
            user_id = interaction.user.id

            if admin_count == 0:
                # First time setup - make this user the global admin
                self._upsert_admin(user_id, 1)

                first_use_embed = discord.Embed(
                    title="🎉 First Time Setup",
                    description=(
                        "This command has been used for the first time and no administrators were found.\n\n"
                        f"**{interaction.user.name}** has been added as the Global Administrator.\n\n"
                        "You can now access all administrative functions."
                    ),
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=first_use_embed, ephemeral=True)
                
                await asyncio.sleep(3)
                
            # Use helper method with automatic fallback
            admin = self._get_admin(user_id)

            # Check if user is global admin or bot owner
            from admin_utils import is_bot_owner
            is_owner = await is_bot_owner(self.bot, user_id)
            
            # Handle both tuple (SQLite) and dict (MongoDB) formats
            if admin:
                if isinstance(admin, tuple):
                    is_global_admin = admin[1] == 1
                elif isinstance(admin, dict):
                    is_global_admin = int(admin.get('is_initial', 0)) == 1
                else:
                    is_global_admin = False
            else:
                is_global_admin = False
            
            if not is_global_admin and not is_owner:
                # User is not a global admin - check if they have Discord admin permissions for first-time setup
                if admin_count == 0 and interaction.guild and (interaction.user.guild_permissions.administrator or interaction.guild.owner_id == interaction.user.id):
                    # First time setup - allow Discord admins to become global admin
                    pass
                else:
                    await interaction.followup.send(
                        "❌ Only **Magnus** can use this command.",
                        ephemeral=True
                    )
                    return

            if admin is None:
                # User is not in database - check if they have Discord admin permissions
                if interaction.guild and (interaction.user.guild_permissions.administrator or interaction.guild.owner_id == interaction.user.id):
                    # Grant admin rights automatically
                    self._upsert_admin(user_id, 1)
                    admin = self._get_admin(user_id)
                else:
                    await interaction.followup.send(
                        "You do not have permission to access this menu.", 
                        ephemeral=True
                    )
                    return


            embed = discord.Embed(
                title="⚙️ Settings Dashboard",
                description=(
                    "**Welcome to the Settings Control Center**\n"
                    "Select a category below to manage your bot configuration\n\n"
                    "╔═══════════════════════════════════╗\n"
                    "║  **📋 Available Categories**      ║\n"
                    "╚═══════════════════════════════════╝\n\n"
                    "🏰 **Alliance Operations**\n"
                    "   ▸ Create, edit, and manage alliances\n"
                    "   ▸ View alliance statistics and settings\n\n"
                    "👥 **Alliance Member Operations**\n"
                    "   ▸ Add, remove, and manage members\n"
                    "   ▸ Track member information\n\n"
                    "📁 **Records**\n"
                    "   ▸ Create custom player records\n"
                    "   ▸ Organize players in custom groups\n\n"
                    "🤖 **Bot Operations**\n"
                    "   ▸ Configure bot behavior and settings\n"
                    "   ▸ Manage bot permissions\n\n"
                    "🎁 **Gift Code Operations**\n"
                    "   ▸ Manage gift codes and rewards\n"
                    "   ▸ Track redemption status\n\n"
                    "📜 **Alliance History**\n"
                    "   ▸ View alliance changes and logs\n"
                    "   ▸ Track historical data\n\n"
                    "🆘 **Support Operations**\n"
                    "   ▸ Access help and support features\n"
                    "   ▸ Troubleshooting tools\n\n"
                    "🔧 **Other Features**\n"
                    "   ▸ Additional utility functions\n"
                    "   ▸ Advanced settings\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=0x7B2CBF
            )

            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Alliance Operations",
                emoji="🏰",
                style=discord.ButtonStyle.primary,
                custom_id=f"alliance_operations:{user_id}",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Member Operations",
                emoji="👥",
                style=discord.ButtonStyle.primary,
                custom_id=f"member_operations:{user_id}",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Records",
                emoji="📁",
                style=discord.ButtonStyle.primary,
                custom_id=f"records_menu:{user_id}",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Bot Operations",
                emoji="🤖",
                style=discord.ButtonStyle.primary,
                custom_id=f"bot_operations:{user_id}",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Gift Code Operations",
                emoji="🎁",
                style=discord.ButtonStyle.primary,
                custom_id=f"gift_operations:{user_id}",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Alliance History",
                emoji="📜",
                style=discord.ButtonStyle.primary,
                custom_id=f"alliance_history:{user_id}",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Support Operations",
                emoji="🆘",
                style=discord.ButtonStyle.primary,
                custom_id=f"support_operations:{user_id}",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Other Features",
                emoji="🔧",
                style=discord.ButtonStyle.primary,
                custom_id=f"other_features:{user_id}",
                row=3
            ))
            view.add_item(discord.ui.Button(
                label="System Status",
                emoji="📊",
                style=discord.ButtonStyle.secondary,
                custom_id=f"system_status:{user_id}",
                row=3
            ))
            view.add_item(discord.ui.Button(
                label="Lock Bot",
                emoji="🔒",
                style=discord.ButtonStyle.danger,
                custom_id=f"lock_bot:{user_id}",
                row=4
            ))

            # Add logo to embed
            embed.set_thumbnail(url="attachment://logo.png")
            
            # Prepare logo file
            logo_file = discord.File("logo.png", filename="logo.png")

            if admin_count == 0:
                await interaction.edit_original_response(embed=embed, view=view, attachments=[logo_file])
            else:
                await interaction.followup.send(embed=embed, view=view, file=logo_file)

        except Exception as e:
            if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                print(f"Settings command error: {e}")
            error_message = "An error occurred while processing your request."
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)





    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id")
            user_id = interaction.user.id

            # Parse owner_id from custom_id if present
            owner_id = user_id
            if custom_id and ":" in custom_id:
                try:
                    real_id, owner_str = custom_id.rsplit(":", 1)
                    # Check if the suffix is a valid user ID (digits)
                    if owner_str.isdigit():
                        check_owner_id = int(owner_str)
                        if user_id != check_owner_id:
                            await interaction.response.send_message("❌ This menu is not for you.", ephemeral=True)
                            return
                        custom_id = real_id
                        owner_id = check_owner_id
                except ValueError:
                    pass
            
            # Use helper method with automatic fallback
            admin = self._get_admin(user_id)
            is_admin = admin is not None
            is_initial = int(admin[1]) if (admin and isinstance(admin, tuple)) else (int(admin.get('is_initial', 0)) if admin else 0)

            # If user is not recognized as admin, attempt to grant if they have Discord admin rights
            if not is_admin:
                if interaction.guild and (interaction.user.guild_permissions.administrator or interaction.guild.owner_id == interaction.user.id):
                    # Grant admin rights in the DB using helper method
                    self._upsert_admin(user_id, 1)
                    is_initial = 1
                    # Refresh admin status after insertion
                    admin = self._get_admin(user_id)
                    is_admin = admin is not None
                else:
                    await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
                    return

            try:
                if custom_id == "alliance_operations":
                    embed = discord.Embed(
                        title="🏰 Alliance Operations Center",
                        description=(
                            "**Manage Your Alliances**\n"
                            "Comprehensive tools for alliance administration\n\n"
                            "╔═══════════════════════════════════╗\n"
                            "║  **⚡ Quick Actions**              ║\n"
                            "╚═══════════════════════════════════╝\n\n"
                            "➕ **Add Alliance**\n"
                            "   ▸ Create a new alliance entry\n"
                            "   ▸ Configure initial settings\n\n"
                            "✏️ **Edit Alliance**\n"
                            "   ▸ Modify alliance configuration\n"
                            "   ▸ Update control intervals\n\n"
                            "🗑️ **Delete Alliance**\n"
                            "   ▸ Remove alliance from database\n"
                            "   ▸ Permanent deletion\n\n"
                            "👀 **View Alliances**\n"
                            "   ▸ List all registered alliances\n"
                            "   ▸ View member counts and settings\n\n"
                            "🔍 **Check Alliance**\n"
                            "   ▸ Run control process manually\n"
                            "   ▸ Verify alliance status\n\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        ),
                        color=0x06B6D4
                    )
                    
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(
                        label="Add Alliance", 
                        emoji="➕",
                        style=discord.ButtonStyle.success, 
                        custom_id=f"add_alliance:{owner_id}", 
                        disabled=is_initial != 1
                    ))
                    view.add_item(discord.ui.Button(
                        label="Edit Alliance", 
                        emoji="✏️",
                        style=discord.ButtonStyle.primary, 
                        custom_id=f"edit_alliance:{owner_id}", 
                        disabled=is_initial != 1
                    ))
                    view.add_item(discord.ui.Button(
                        label="Delete Alliance", 
                        emoji="🗑️",
                        style=discord.ButtonStyle.danger, 
                        custom_id=f"delete_alliance:{owner_id}", 
                        disabled=is_initial != 1
                    ))
                    view.add_item(discord.ui.Button(
                        label="View Alliances", 
                        emoji="👀",
                        style=discord.ButtonStyle.primary, 
                        custom_id=f"view_alliances:{owner_id}"
                    ))
                    view.add_item(discord.ui.Button(
                        label="Check Alliance", 
                        emoji="🔍",
                        style=discord.ButtonStyle.primary, 
                        custom_id=f"check_alliance:{owner_id}"
                    ))
                    view.add_item(discord.ui.Button(
                        label="Main Menu", 
                        emoji="🏠",
                        style=discord.ButtonStyle.secondary, 
                        custom_id=f"main_menu:{owner_id}"
                    ))

                    await interaction.response.edit_message(embed=embed, view=view)

                elif custom_id == "edit_alliance":
                    if is_initial != 1:
                        await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
                        return
                    await self.edit_alliance(interaction)

                elif custom_id == "check_alliance":
                    self.c.execute("""
                        SELECT a.alliance_id, a.name, COALESCE(s.interval, 0) as interval
                        FROM alliance_list a
                        LEFT JOIN alliancesettings s ON a.alliance_id = s.alliance_id
                        ORDER BY a.name
                    """)
                    alliances = self.c.fetchall()

                    if not alliances:
                        await interaction.response.send_message("No alliances found to check.", ephemeral=True)
                        return

                    options = [
                        discord.SelectOption(
                            label="Check All Alliances",
                            value="all",
                            description="Start control process for all alliances",
                            emoji="🔄"
                        )
                    ]
                    
                    options.extend([
                        discord.SelectOption(
                            label=f"{name[:40]}",
                            value=str(alliance_id),
                            description=f"Control Interval: {interval} minutes"
                        ) for alliance_id, name, interval in alliances
                    ])

                    select = discord.ui.Select(
                        placeholder="Select an alliance to check",
                        options=options,
                        custom_id="alliance_check_select"
                    )

                    async def alliance_check_callback(select_interaction: discord.Interaction):
                        if select_interaction.user.id != owner_id:
                            await select_interaction.response.send_message("❌ This menu is not for you.", ephemeral=True)
                            return
                        try:
                            selected_value = select_interaction.data["values"][0]
                            control_cog = self.bot.get_cog('Control')
                            
                            if not control_cog:
                                await select_interaction.response.send_message("Control module not found.", ephemeral=True)
                                return
                            
                            # Ensure the centralized queue processor is running
                            await control_cog.login_handler.start_queue_processor()
                            
                            if selected_value == "all":
                                progress_embed = discord.Embed(
                                    title="🔄 Alliance Control Queue",
                                    description=(
                                        "**Control Queue Information**\n"
                                        "╔═══════════════════════════════════╗\n"
                                        "║  **📊 Queue Status**              ║\n"
                                        "╚═══════════════════════════════════╝\n\n"
                                        f"📊 **Total Alliances:** `{len(alliances)}`\n"
                                        "🔄 **Status:** `Adding to queue...`\n"
                                        "⏰ **Queue Start:** `Now`\n\n"
                                        "⚠️ **Processing Info**\n"
                                        "   ▸ Sequential processing\n"
                                        "   ▸ 1 minute between controls\n\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                        "⌛ Please wait while processing..."
                                    ),
                                    color=0x06B6D4
                                )
                                await select_interaction.response.send_message(embed=progress_embed)
                                msg = await select_interaction.original_response()
                                message_id = msg.id

                                # Queue all alliance operations at once
                                queued_alliances = []
                                for index, (alliance_id, name, _) in enumerate(alliances):
                                    try:
                                        self.c.execute("""
                                            SELECT channel_id FROM alliancesettings WHERE alliance_id = ?
                                        """, (alliance_id,))
                                        channel_data = self.c.fetchone()
                                        channel = self.bot.get_channel(channel_data[0]) if channel_data else select_interaction.channel
                                        
                                        await control_cog.login_handler.queue_operation({
                                            'type': 'alliance_control',
                                            'callback': lambda ch=channel, aid=alliance_id, inter=select_interaction: control_cog.check_agslist(ch, aid, interaction=inter),
                                            'description': f'Manual control check for alliance {name}',
                                            'alliance_id': alliance_id,
                                            'interaction': select_interaction
                                        })
                                        queued_alliances.append((alliance_id, name))
                                    
                                    except Exception as e:
                                        print(f"Error queuing alliance {name}: {e}")
                                        continue
                                
                                # Update status to show all alliances have been queued
                                queue_status_embed = discord.Embed(
                                    title="🔄 Alliance Control Queue",
                                    description=(
                                        "**Control Queue Information**\n"
                                        "╔═══════════════════════════════════╗\n"
                                        "║  **✅ Queue Ready**               ║\n"
                                        "╚═══════════════════════════════════╝\n\n"
                                        f"📊 **Total Alliances Queued:** `{len(queued_alliances)}`\n"
                                        f"⏰ **Queue Start:** <t:{int(datetime.now().timestamp())}:R>\n\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                        "⌛ All controls queued and will process in order..."
                                    ),
                                    color=0x06B6D4
                                )
                                channel = select_interaction.channel
                                msg = await channel.fetch_message(message_id)
                                await msg.edit(embed=queue_status_embed)
                                
                                # Monitor queue completion
                                start_time = datetime.now()
                                while True:
                                    queue_info = control_cog.login_handler.get_queue_info()
                                    
                                    # Check if all our operations are done
                                    if queue_info['queue_size'] == 0 and queue_info['current_operation'] is None:
                                        # Double-check by waiting a moment
                                        await asyncio.sleep(2)
                                        queue_info = control_cog.login_handler.get_queue_info()
                                        if queue_info['queue_size'] == 0 and queue_info['current_operation'] is None:
                                            break
                                    
                                    # Update status periodically
                                    if queue_info['current_operation'] and queue_info['current_operation'].get('type') == 'alliance_control':
                                        current_alliance_id = queue_info['current_operation'].get('alliance_id')
                                        current_name = next((name for aid, name in queued_alliances if aid == current_alliance_id), "Unknown")
                                        
                                        update_embed = discord.Embed(
                                            title="🔄 Alliance Control Queue",
                                            description=(
                                                "**Control Queue Information**\n"
                                                "╔═══════════════════════════════════╗\n"
                                                "║  **⚡ Processing**                ║\n"
                                                "╚═══════════════════════════════════╝\n\n"
                                                f"📊 **Total Alliances:** `{len(queued_alliances)}`\n"
                                                f"🔄 **Currently Processing:** `{current_name}`\n"
                                                f"📈 **Queue Remaining:** `{queue_info['queue_size']}`\n"
                                                f"⏰ **Started:** <t:{int(start_time.timestamp())}:R>\n\n"
                                                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                                "⌛ Processing controls..."
                                            ),
                                            color=0x06B6D4
                                        )
                                        await msg.edit(embed=update_embed)
                                    
                                    await asyncio.sleep(5)  # Check every 5 seconds
                                
                                # All operations complete
                                queue_complete_embed = discord.Embed(
                                    title="✅ Alliance Control Queue Complete",
                                    description=(
                                        "**Queue Status Information**\n"
                                        "╔═══════════════════════════════════╗\n"
                                        "║  **✅ All Complete**              ║\n"
                                        "╚═══════════════════════════════════╝\n\n"
                                        f"📊 **Total Alliances Processed:** `{len(queued_alliances)}`\n"
                                        "🔄 **Status:** `All controls completed`\n"
                                        f"⏰ **Completion Time:** <t:{int(datetime.now().timestamp())}:R>\n"
                                        f"⏱️ **Total Duration:** `{int((datetime.now() - start_time).total_seconds())} seconds`\n\n"
                                        "📝 **Note:** Control results shared in respective channels\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                    ),
                                    color=0x10B981
                                )
                                await msg.edit(embed=queue_complete_embed)
                            
                            else:
                                alliance_id = int(selected_value)
                                self.c.execute("""
                                    SELECT a.name, s.channel_id 
                                    FROM alliance_list a
                                    LEFT JOIN alliancesettings s ON a.alliance_id = s.alliance_id
                                    WHERE a.alliance_id = ?
                                """, (alliance_id,))
                                alliance_data = self.c.fetchone()

                                if not alliance_data:
                                    await select_interaction.response.send_message("Alliance not found.", ephemeral=True)
                                    return

                                alliance_name, channel_id = alliance_data
                                channel = self.bot.get_channel(channel_id) if channel_id else select_interaction.channel
                                
                                status_embed = discord.Embed(
                                    title="🔍 Alliance Control",
                                    description=(
                                        "**Control Information**\n"
                                        "╔═══════════════════════════════════╗\n"
                                        "║  **⏳ Queued**                    ║\n"
                                        "╚═══════════════════════════════════╝\n\n"
                                        f"📊 **Alliance:** `{alliance_name}`\n"
                                        f"🔄 **Status:** `Queued`\n"
                                        f"⏰ **Queue Time:** `Now`\n"
                                        f"📢 **Results Channel:** `{channel.name if channel else 'Designated channel'}`\n\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                        "⏳ Alliance control will begin shortly..."
                                    ),
                                    color=0x06B6D4
                                )
                                await select_interaction.response.send_message(embed=status_embed)
                                
                                await control_cog.login_handler.queue_operation({
                                    'type': 'alliance_control',
                                    'callback': lambda ch=channel, aid=alliance_id: control_cog.check_agslist(ch, aid),
                                    'description': f'Manual control check for alliance {alliance_name}',
                                    'alliance_id': alliance_id
                                })

                        except Exception as e:
                            print(f"Alliance check error: {e}")
                            await select_interaction.response.send_message(
                                "An error occurred during the control process.", 
                                ephemeral=True
                            )

                    select.callback = alliance_check_callback
                    view = discord.ui.View()
                    view.add_item(select)

                    embed = discord.Embed(
                        title="🔍 Alliance Control Center",
                        description=(
                            "**Select Alliance to Control**\n"
                            "Choose an alliance to run the control process\n\n"
                            "╔═══════════════════════════════════╗\n"
                            "║  **ℹ️ Important Information**     ║\n"
                            "╚═══════════════════════════════════╝\n\n"
                            "🔄 **Check All Alliances**\n"
                            "   ▸ Process all registered alliances\n"
                            "   ▸ Sequential execution with 1-min intervals\n\n"
                            "⏱️ **Processing Time**\n"
                            "   ▸ May take several minutes to complete\n"
                            "   ▸ Progress updates will be shown\n\n"
                            "📢 **Results**\n"
                            "   ▸ Shared in designated alliance channels\n"
                            "   ▸ Other controls queued during process\n\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        ),
                        color=0x06B6D4
                    )
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

                elif custom_id == "member_operations":
                    await self.bot.get_cog("AllianceMemberOperations").handle_member_operations(interaction)

                elif custom_id == "bot_operations":
                    try:
                        bot_ops_cog = interaction.client.get_cog("BotOperations")
                        if bot_ops_cog:
                            await bot_ops_cog.show_bot_operations_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Bot Operations module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                            print(f"Bot operations error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Bot Operations.",
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Bot Operations.",
                                ephemeral=True
                            )

                elif custom_id == "gift_operations":
                    try:
                        gift_ops_cog = interaction.client.get_cog("GiftOperations")
                        if gift_ops_cog:
                            await gift_ops_cog.show_gift_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Gift Operations module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        print(f"Gift operations error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Gift Operations.",
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Gift Operations.",
                                ephemeral=True
                            )

                elif custom_id == "add_alliance":
                    if not is_admin:
                        await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
                        return
                    await self.add_alliance(interaction)

                elif custom_id == "delete_alliance":
                    if not is_admin:
                        await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
                        return
                    await self.delete_alliance(interaction)

                elif custom_id == "view_alliances":
                    await self.view_alliances(interaction)

                elif custom_id == "support_operations":
                    try:
                        support_ops_cog = interaction.client.get_cog("SupportOperations")
                        if support_ops_cog:
                            await support_ops_cog.show_support_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Support Operations module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                            print(f"Support operations error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Support Operations.", 
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Support Operations.",
                                ephemeral=True
                            )

                elif custom_id == "alliance_history":
                    try:
                        changes_cog = interaction.client.get_cog("Changes")
                        if changes_cog:
                            await changes_cog.show_alliance_history_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Alliance History module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        print(f"Alliance history error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Alliance History.",
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Alliance History.",
                                ephemeral=True
                            )

                elif custom_id == "lock_bot":
                    # Only global admins can lock/unlock bot
                    if is_initial != 1:
                        await interaction.response.send_message(
                            "❌ Only Global Administrators can lock/unlock the bot.",
                            ephemeral=True
                        )
                        return
                    
                    try:
                        # Show server selection for locking
                        all_guilds = list(self.bot.guilds)
                        
                        if not all_guilds:
                            await interaction.response.send_message(
                                "❌ Bot is not in any servers.",
                                ephemeral=True
                            )
                            return
                        
                        # Get current lock status for all servers
                        self.c_settings.execute("SELECT guild_id, locked FROM server_locks")
                        lock_status = {row[0]: row[1] for row in self.c_settings.fetchall()}
                        
                        # Create paginated server view
                        servers_per_page = 25
                        total_pages = (len(all_guilds) + servers_per_page - 1) // servers_per_page
                        
                        class ServerLockView(discord.ui.View):
                            def __init__(self, guilds_list, current_page=0):
                                super().__init__(timeout=180)
                                self.guilds = guilds_list
                                self.current_page = current_page
                                self.total_pages = total_pages
                                
                                # Add server selection dropdown
                                start_idx = current_page * servers_per_page
                                end_idx = min(start_idx + servers_per_page, len(guilds_list))
                                
                                server_options = []
                                for guild in guilds_list[start_idx:end_idx]:
                                    is_locked = lock_status.get(guild.id, 0) == 1
                                    lock_emoji = "🔒" if is_locked else "🔓"
                                    server_options.append(
                                        discord.SelectOption(
                                            label=f"{guild.name[:90]}",
                                            value=str(guild.id),
                                            description=f"{lock_emoji} {'Locked' if is_locked else 'Unlocked'}",
                                            emoji=lock_emoji
                                        )
                                    )
                                
                                server_select = discord.ui.Select(
                                    placeholder="Select a server to lock/unlock...",
                                    options=server_options,
                                    custom_id="server_lock_select",
                                    row=0
                                )
                                server_select.callback = self.server_selected
                                self.add_item(server_select)
                                
                                # Add pagination buttons if needed
                                if total_pages > 1:
                                    if current_page > 0:
                                        prev_button = discord.ui.Button(
                                            label="◀ Previous",
                                            style=discord.ButtonStyle.secondary,
                                            custom_id="prev_page_lock",
                                            row=1
                                        )
                                        prev_button.callback = self.previous_page
                                        self.add_item(prev_button)
                                    
                                    if current_page < total_pages - 1:
                                        next_button = discord.ui.Button(
                                            label="Next ▶",
                                            style=discord.ButtonStyle.secondary,
                                            custom_id="next_page_lock",
                                            row=1
                                        )
                                        next_button.callback = self.next_page
                                        self.add_item(next_button)
                                
                                # Add back to main menu button
                                back_button = discord.ui.Button(
                                    label="◀ Main Menu",
                                    emoji="🏠",
                                    style=discord.ButtonStyle.secondary,
                                    custom_id="main_menu_lock",
                                    row=2
                                )
                                back_button.callback = self.back_to_menu
                                self.add_item(back_button)
                            
                            async def previous_page(self, button_interaction: discord.Interaction):
                                new_page = max(0, self.current_page - 1)
                                new_view = ServerLockView(self.guilds, new_page)
                                embed = self.create_embed(new_page)
                                await button_interaction.response.edit_message(embed=embed, view=new_view)
                            
                            async def next_page(self, button_interaction: discord.Interaction):
                                new_page = min(self.total_pages - 1, self.current_page + 1)
                                new_view = ServerLockView(self.guilds, new_page)
                                embed = self.create_embed(new_page)
                                await button_interaction.response.edit_message(embed=embed, view=new_view)
                            
                            async def back_to_menu(self, button_interaction: discord.Interaction):
                                await button_interaction.response.defer()
                                # Redirect to settings menu
                                from cogs.alliance import Alliance
                                alliance_cog = button_interaction.client.get_cog("Alliance")
                                if alliance_cog:
                                    await alliance_cog.show_main_menu(button_interaction)
                            
                            def create_embed(self, page):
                                start_idx = page * servers_per_page
                                end_idx = min(start_idx + servers_per_page, len(self.guilds))
                                
                                server_list = ""
                                for idx, guild in enumerate(self.guilds[start_idx:end_idx], start=start_idx + 1):
                                    is_locked = lock_status.get(guild.id, 0) == 1
                                    lock_emoji = "🔒" if is_locked else "🔓"
                                    status = "**LOCKED**" if is_locked else "Unlocked"
                                    server_list += f"**{idx:02d}.** {lock_emoji} {guild.name}\n└ Status: {status}\n\n"
                                
                                embed = discord.Embed(
                                    title="🔒 Server Lock Management",
                                    description=(
                                        "```ansi\n"
                                        "\u001b[2;31m╔═══════════════════════════════════╗\n"
                                        "\u001b[2;31m║  \u001b[1;37mSECURITY CONTROL\u001b[0m\u001b[2;31m              ║\n"
                                        "\u001b[2;31m╚═══════════════════════════════════╝\u001b[0m\n"
                                        "```\n"
                                        "**Select a server to lock or unlock the bot**\n\n"
                                        "🔒 **Locked**: Bot will not respond to commands\n"
                                        "🔓 **Unlocked**: Bot functions normally\n\n"
                                        f"{server_list}"
                                    ),
                                    color=0xED4245
                                )
                                
                                if self.total_pages > 1:
                                    embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
                                else:
                                    embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
                                
                                return embed
                            
                            async def server_selected(self, select_interaction: discord.Interaction):
                                guild_id = int(select_interaction.data["values"][0])
                                guild = discord.utils.get(self.guilds, id=guild_id)
                                
                                if not guild:
                                    await select_interaction.response.send_message(
                                        "❌ Server not found.",
                                        ephemeral=True
                                    )
                                    return
                                
                                # Get current lock status using local connection
                                import sqlite3
                                settings_db = sqlite3.connect('db/settings.sqlite')
                                cursor = settings_db.cursor()
                                cursor.execute(
                                    "SELECT locked FROM server_locks WHERE guild_id = ?",
                                    (guild_id,)
                                )
                                result = cursor.fetchone()
                                is_locked = result[0] == 1 if result else False
                                settings_db.close()
                                
                                # Create lock/unlock confirmation view
                                confirm_view = discord.ui.View(timeout=60)
                                
                                if is_locked:
                                    # Show unlock button
                                    unlock_button = discord.ui.Button(
                                        label="Unlock Bot",
                                        emoji="🔓",
                                        style=discord.ButtonStyle.success,
                                        custom_id="unlock_confirm"
                                    )
                                    
                                    async def unlock_callback(btn_interaction: discord.Interaction):
                                        # Unlock the server
                                        import sqlite3
                                        settings_db = sqlite3.connect('db/settings.sqlite')
                                        cursor = settings_db.cursor()
                                        cursor.execute(
                                            "INSERT OR REPLACE INTO server_locks (guild_id, locked, locked_by, locked_at) VALUES (?, 0, ?, CURRENT_TIMESTAMP)",
                                            (guild_id, btn_interaction.user.id)
                                        )
                                        settings_db.commit()
                                        settings_db.close()
                                        
                                        # Update lock_status dict
                                        lock_status[guild_id] = 0
                                        
                                        success_embed = discord.Embed(
                                            title="✅ Bot Unlocked",
                                            description=(
                                                f"**Server:** {guild.name}\n"
                                                f"**Status:** 🔓 Unlocked\n\n"
                                                "The bot will now respond normally in this server."
                                            ),
                                            color=0x57F287
                                        )
                                        success_embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
                                        
                                        await btn_interaction.response.edit_message(
                                            embed=success_embed,
                                            view=None
                                        )
                                    
                                    unlock_button.callback = unlock_callback
                                    confirm_view.add_item(unlock_button)
                                else:
                                    # Show lock button
                                    lock_button = discord.ui.Button(
                                        label="Lock Bot",
                                        emoji="🔒",
                                        style=discord.ButtonStyle.danger,
                                        custom_id="lock_confirm"
                                    )
                                    
                                    async def lock_callback(btn_interaction: discord.Interaction):
                                        # Lock the server
                                        import sqlite3
                                        settings_db = sqlite3.connect('db/settings.sqlite')
                                        cursor = settings_db.cursor()
                                        cursor.execute(
                                            "INSERT OR REPLACE INTO server_locks (guild_id, locked, locked_by, locked_at) VALUES (?, 1, ?, CURRENT_TIMESTAMP)",
                                            (guild_id, btn_interaction.user.id)
                                        )
                                        settings_db.commit()
                                        settings_db.close()
                                        
                                        # Update lock_status dict
                                        lock_status[guild_id] = 1
                                        
                                        success_embed = discord.Embed(
                                            title="🔒 Bot Locked",
                                            description=(
                                                f"**Server:** {guild.name}\n"
                                                f"**Status:** 🔒 Locked\n\n"
                                                "The bot will no longer respond to commands in this server.\n"
                                                "A locked message will be sent when users try to use commands."
                                            ),
                                            color=0xED4245
                                        )
                                        success_embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
                                        
                                        await btn_interaction.response.edit_message(
                                            embed=success_embed,
                                            view=None
                                        )
                                    
                                    lock_button.callback = lock_callback
                                    confirm_view.add_item(lock_button)
                                
                                # Add cancel button
                                cancel_button = discord.ui.Button(
                                    label="Cancel",
                                    emoji="❌",
                                    style=discord.ButtonStyle.secondary,
                                    custom_id="cancel_lock"
                                )
                                
                                async def cancel_callback(btn_interaction: discord.Interaction):
                                    await btn_interaction.response.edit_message(
                                        content="❌ Operation cancelled.",
                                        embed=None,
                                        view=None
                                    )
                                
                                cancel_button.callback = cancel_callback
                                confirm_view.add_item(cancel_button)
                                
                                # Show confirmation
                                confirm_embed = discord.Embed(
                                    title=f"{'🔓 Unlock' if is_locked else '🔒 Lock'} Bot",
                                    description=(
                                        f"**Server:** {guild.name}\n"
                                        f"**Current Status:** {'🔒 Locked' if is_locked else '🔓 Unlocked'}\n\n"
                                        f"Do you want to **{'unlock' if is_locked else 'lock'}** the bot for this server?"
                                    ),
                                    color=0x57F287 if is_locked else 0xED4245
                                )
                                
                                await select_interaction.response.send_message(
                                    embed=confirm_embed,
                                    view=confirm_view,
                                    ephemeral=True
                                )
                        
                        # Create and send initial view
                        view = ServerLockView(all_guilds, 0)
                        embed = view.create_embed(0)
                        
                        await interaction.response.send_message(
                            embed=embed,
                            view=view,
                            ephemeral=True
                        )
                        
                    except Exception as e:
                        print(f"Lock bot error: {e}")
                        import traceback
                        traceback.print_exc()
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "❌ An error occurred while loading the lock management interface.",
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "❌ An error occurred while loading the lock management interface.",
                                ephemeral=True
                            )

                elif custom_id == "system_status":
                    await self.handle_system_status(interaction)

                elif custom_id == "other_features":
                    try:
                        other_features_cog = interaction.client.get_cog("OtherFeatures")
                        if other_features_cog:
                            await other_features_cog.show_other_features_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Other Features module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                            print(f"Other features error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Other Features menu.",
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Other Features menu.",
                                ephemeral=True
                            )

            except Exception as e:
                if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                    print(f"Error processing interaction with custom_id '{custom_id}': {e}")
                
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred while processing your request. Please try again.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "An error occurred while processing your request. Please try again.",
                        ephemeral=True
                    )

    async def handle_system_status(self, interaction: discord.Interaction):
        """Displays the system status dashboard"""
        try:
            status = self._get_system_status()
            
            embed = discord.Embed(
                title="📊 System Performance Dashboard",
                description=(
                    "**Technical Metrics & Bot Health**\n"
                    "╔═══════════════════════════════════╗\n"
                    "║  **🚀 Bot Status**                ║\n"
                    "╚═══════════════════════════════════╝\n\n"
                    f"⚡ **CPU Usage:** `{status['cpu']}%`\n"
                    f"🧠 **RAM Usage:** `{status['ram_used']:.2f}GB / {status['ram_total']:.2f}GB` ({status['ram_percent']}%)\n"
                    f"💾 **Disk Usage:** `{status['disk_used']:.2f}GB / {status['disk_total']:.2f}GB` ({status['disk_percent']}%)\n\n"
                    "╔═══════════════════════════════════╗\n"
                    "║  **⏱️ Performance**               ║\n"
                    "╚═══════════════════════════════════╝\n\n"
                    f"🕒 **Uptime:** `{status['uptime']}`\n"
                    f"📡 **Latency:** `{round(self.bot.latency * 1000)}ms`\n"
                    f"🖥️ **OS:** `{status['os']}`\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=0x06B6D4,
                timestamp=datetime.now()
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Refresh", 
                emoji="🔄",
                style=discord.ButtonStyle.primary,
                custom_id=f"system_status:{interaction.user.id}"
            ))
            view.add_item(discord.ui.Button(
                label="Main Menu",
                emoji="🏠",
                style=discord.ButtonStyle.secondary,
                custom_id=f"main_menu:{interaction.user.id}"
            ))
            
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=view)
            else:
                await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            print(f"Error showing system status: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error fetching system metrics.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Error fetching system metrics.", ephemeral=True)

    def _get_system_status(self):
        """Helper to fetch system metrics using psutil"""
        import psutil
        import platform
        
        # CPU
        cpu = psutil.cpu_percent(interval=None)
        
        # RAM
        mem = psutil.virtual_memory()
        ram_used = mem.used / (1024 ** 3)
        ram_total = mem.total / (1024 ** 3)
        ram_percent = mem.percent
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_used = disk.used / (1024 ** 3)
        disk_total = disk.total / (1024 ** 3)
        disk_percent = disk.percent
        
        # Uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        return {
            "cpu": cpu,
            "ram_used": ram_used,
            "ram_total": ram_total,
            "ram_percent": ram_percent,
            "disk_used": disk_used,
            "disk_total": disk_total,
            "disk_percent": disk_percent,
            "uptime": str(uptime).split('.')[0],
            "os": platform.system()
        }

    async def add_alliance(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Please perform this action in a Discord channel.", ephemeral=True)
            return

        modal = AllianceModal(title="Add Alliance")
        await interaction.response.send_modal(modal)
        await modal.wait()

        try:
            alliance_name = modal.name.value.strip()
            interval = int(modal.interval.value.strip())

            embed = discord.Embed(
                title="📢 Channel Selection",
                description=(
                    "**Select Alliance Channel**\n"
                    "╔═══════════════════════════════════╗\n"
                    "║  **ℹ️ Instructions**              ║\n"
                    "╚═══════════════════════════════════╝\n\n"
                    "Please select a channel for the alliance\n\n"
                    f"**📊 Total Channels:** {len(interaction.guild.text_channels)}\n"
                    "**📄 Page:** 1/1"
                ),
                color=0x06B6D4
            )

            async def channel_select_callback(select_interaction: discord.Interaction):
                try:
                    self.c.execute("SELECT alliance_id FROM alliance_list WHERE name = ?", (alliance_name,))
                    existing_alliance = self.c.fetchone()
                    
                    if existing_alliance:
                        error_embed = discord.Embed(
                            title="Error",
                            description="An alliance with this name already exists.",
                            color=discord.Color.red()
                        )
                        await select_interaction.response.edit_message(embed=error_embed, view=None)
                        return

                    channel_id = int(select_interaction.data["values"][0])

                    self.c.execute("INSERT INTO alliance_list (name, discord_server_id) VALUES (?, ?)", 
                                 (alliance_name, interaction.guild.id))
                    alliance_id = self.c.lastrowid
                    self.c.execute("INSERT INTO alliancesettings (alliance_id, channel_id, interval) VALUES (?, ?, ?)", 
                                 (alliance_id, channel_id, interval))
                    self.conn.commit()
                    if mongo_enabled():
                        try:
                            AlliancesAdapter.upsert(alliance_id, alliance_name, interaction.guild.id)
                            AllianceSettingsAdapter.upsert(alliance_id, channel_id, interval, giftcodecontrol=1)
                        except Exception:
                            pass

                    self.c_giftcode.execute("""
                        INSERT INTO giftcodecontrol (alliance_id, status) 
                        VALUES (?, 1)
                    """, (alliance_id,))
                    self.conn_giftcode.commit()

                    result_embed = discord.Embed(
                        title="✅ Alliance Created Successfully",
                        description="The alliance has been created with the following details:",
                        color=0x10B981
                    )
                    
                    info_section = (
                        f"**🛡️ Alliance Name**\n{alliance_name}\n\n"
                        f"**🔢 Alliance ID**\n{alliance_id}\n\n"
                        f"**📢 Channel**\n<#{channel_id}>\n\n"
                        f"**⏱️ Control Interval**\n{interval} minutes"
                    )
                    result_embed.add_field(name="Alliance Details", value=info_section, inline=False)
                    
                    result_embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
                    result_embed.timestamp = discord.utils.utcnow()
                    
                    await select_interaction.response.edit_message(embed=result_embed, view=None)

                except Exception as e:
                    error_embed = discord.Embed(
                        title="Error",
                        description=f"Error creating alliance: {str(e)}",
                        color=discord.Color.red()
                    )
                    await select_interaction.response.edit_message(embed=error_embed, view=None)

            channels = interaction.guild.text_channels
            view = PaginatedChannelView(channels, channel_select_callback)
            await modal.interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except ValueError:
            error_embed = discord.Embed(
                title="Error",
                description="Invalid interval value. Please enter a number.",
                color=discord.Color.red()
            )
            await modal.interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"Error: {str(e)}",
                color=discord.Color.red()
            )
            await modal.interaction.response.send_message(embed=error_embed, ephemeral=True)

    async def edit_alliance(self, interaction: discord.Interaction):
        self.c.execute("""
            SELECT a.alliance_id, a.name, COALESCE(s.interval, 0) as interval, COALESCE(s.channel_id, 0) as channel_id 
            FROM alliance_list a 
            LEFT JOIN alliancesettings s ON a.alliance_id = s.alliance_id
            ORDER BY a.alliance_id ASC
        """)
        alliances = self.c.fetchall()
        
        if not alliances:
            no_alliance_embed = discord.Embed(
                title="❌ No Alliances Found",
                description=(
                    "There are no alliances registered in the database.\n"
                    "Please create an alliance first using the `/alliance create` command."
                ),
                color=discord.Color.red()
            )
            no_alliance_embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
            return await interaction.response.send_message(embed=no_alliance_embed, ephemeral=True)

        alliance_options = [
            discord.SelectOption(
                label=f"{name} (ID: {alliance_id})",
                value=f"{alliance_id}",
                description=f"Interval: {interval} minutes"
            ) for alliance_id, name, interval, _ in alliances
        ]
        
        items_per_page = 25
        option_pages = [alliance_options[i:i + items_per_page] for i in range(0, len(alliance_options), items_per_page)]
        total_pages = len(option_pages)

        class PaginatedAllianceView(discord.ui.View):
            def __init__(self, pages, original_callback):
                super().__init__(timeout=7200)
                self.current_page = 0
                self.pages = pages
                self.original_callback = original_callback
                self.total_pages = len(pages)
                self.update_view()

            def update_view(self):
                self.clear_items()
                
                select = discord.ui.Select(
                    placeholder=f"Select alliance ({self.current_page + 1}/{self.total_pages})",
                    options=self.pages[self.current_page]
                )
                select.callback = self.original_callback
                self.add_item(select)
                
                previous_button = discord.ui.Button(
                    label="◀️",
                    style=discord.ButtonStyle.grey,
                    custom_id="previous",
                    disabled=(self.current_page == 0)
                )
                previous_button.callback = self.previous_callback
                self.add_item(previous_button)

                next_button = discord.ui.Button(
                    label="▶️",
                    style=discord.ButtonStyle.grey,
                    custom_id="next",
                    disabled=(self.current_page == len(self.pages) - 1)
                )
                next_button.callback = self.next_callback
                self.add_item(next_button)

            async def previous_callback(self, interaction: discord.Interaction):
                self.current_page = (self.current_page - 1) % len(self.pages)
                self.update_view()
                
                embed = interaction.message.embeds[0]
                embed.description = (
                    "**Instructions:**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "1️⃣ Select an alliance from the dropdown menu\n"
                    "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                    f"**Current Page:** {self.current_page + 1}/{self.total_pages}\n"
                    f"**Total Alliances:** {sum(len(page) for page in self.pages)}\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                )
                await interaction.response.edit_message(embed=embed, view=self)

            async def next_callback(self, interaction: discord.Interaction):
                self.current_page = (self.current_page + 1) % len(self.pages)
                self.update_view()
                
                embed = interaction.message.embeds[0]
                embed.description = (
                    "**Instructions:**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "1️⃣ Select an alliance from the dropdown menu\n"
                    "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                    f"**Current Page:** {self.current_page + 1}/{self.total_pages}\n"
                    f"**Total Alliances:** {sum(len(page) for page in self.pages)}\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                )
                await interaction.response.edit_message(embed=embed, view=self)

        async def select_callback(select_interaction: discord.Interaction):
            try:
                alliance_id = int(select_interaction.data["values"][0])
                alliance_data = next(a for a in alliances if a[0] == alliance_id)
                
                self.c.execute("""
                    SELECT interval, channel_id 
                    FROM alliancesettings 
                    WHERE alliance_id = ?
                """, (alliance_id,))
                settings_data = self.c.fetchone()
                
                modal = AllianceModal(
                    title="Edit Alliance",
                    default_name=alliance_data[1],
                    default_interval=str(settings_data[0] if settings_data else 0)
                )
                await select_interaction.response.send_modal(modal)
                await modal.wait()

                try:
                    alliance_name = modal.name.value.strip()
                    interval = int(modal.interval.value.strip())

                    embed = discord.Embed(
                        title="🔄 Channel Selection",
                        description=(
                            "**Current Channel Information**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📢 Current channel: {f'<#{settings_data[1]}>' if settings_data else 'Not set'}\n"
                            "**Page:** 1/1\n"
                            f"**Total Channels:** {len(interaction.guild.text_channels)}\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                        ),
                        color=discord.Color.blue()
                    )

                    async def channel_select_callback(channel_interaction: discord.Interaction):
                        try:
                            channel_id = int(channel_interaction.data["values"][0])

                            self.c.execute("UPDATE alliance_list SET name = ? WHERE alliance_id = ?", 
                                          (alliance_name, alliance_id))

                            if settings_data:
                                self.c.execute("""
                                    UPDATE alliancesettings 
                                    SET channel_id = ?, interval = ? 
                                    WHERE alliance_id = ?
                                """, (channel_id, interval, alliance_id))
                            else:
                                self.c.execute("""
                                    INSERT INTO alliancesettings (alliance_id, channel_id, interval)
                                    VALUES (?, ?, ?)
                                """, (alliance_id, channel_id, interval))
                            
                            self.conn.commit()
                            if mongo_enabled():
                                try:
                                    AlliancesAdapter.upsert(alliance_id, alliance_name, interaction.guild.id)
                                    AllianceSettingsAdapter.upsert(alliance_id, channel_id, interval)
                                except Exception:
                                    pass

                            result_embed = discord.Embed(
                                title="✅ Alliance Successfully Updated",
                                description="The alliance details have been updated as follows:",
                                color=discord.Color.green()
                            )
                            
                            info_section = (
                                f"**🛡️ Alliance Name**\n{alliance_name}\n\n"
                                f"**🔢 Alliance ID**\n{alliance_id}\n\n"
                                f"**📢 Channel**\n<#{channel_id}>\n\n"
                                f"**⏱️ Control Interval**\n{interval} minutes"
                            )
                            result_embed.add_field(name="Alliance Details", value=info_section, inline=False)
                            
                            result_embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
                            result_embed.timestamp = discord.utils.utcnow()
                            
                            await channel_interaction.response.edit_message(embed=result_embed, view=None)

                        except Exception as e:
                            error_embed = discord.Embed(
                                title="❌ Error",
                                description=f"An error occurred while updating the alliance: {str(e)}",
                                color=discord.Color.red()
                            )
                            await channel_interaction.response.edit_message(embed=error_embed, view=None)

                    channels = interaction.guild.text_channels
                    view = PaginatedChannelView(channels, channel_select_callback)
                    await modal.interaction.response.send_message(embed=embed, view=view, ephemeral=True)

                except ValueError:
                    error_embed = discord.Embed(
                        title="Error",
                        description="Invalid interval value. Please enter a number.",
                        color=discord.Color.red()
                    )
                    await modal.interaction.response.send_message(embed=error_embed, ephemeral=True)
                except Exception as e:
                    error_embed = discord.Embed(
                        title="Error",
                        description=f"Error: {str(e)}",
                        color=discord.Color.red()
                    )
                    await modal.interaction.response.send_message(embed=error_embed, ephemeral=True)

            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                if not select_interaction.response.is_done():
                    await select_interaction.response.send_message(embed=error_embed, ephemeral=True)
                else:
                    await select_interaction.followup.send(embed=error_embed, ephemeral=True)

        view = PaginatedAllianceView(option_pages, select_callback)
        embed = discord.Embed(
            title="🛡️ Alliance Edit Menu",
            description=(
                "**Instructions:**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "1️⃣ Select an alliance from the dropdown menu\n"
                "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                f"**Current Page:** {1}/{total_pages}\n"
                f"**Total Alliances:** {len(alliances)}\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def delete_alliance(self, interaction: discord.Interaction):
        try:
            self.c.execute("SELECT alliance_id, name FROM alliance_list ORDER BY name")
            alliances = self.c.fetchall()
            
            if not alliances:
                no_alliance_embed = discord.Embed(
                    title="❌ No Alliances Found",
                    description="There are no alliances to delete.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=no_alliance_embed, ephemeral=True)
                return

            alliance_members = {}
            for alliance_id, _ in alliances:
                self.c_users.execute("SELECT COUNT(*) FROM users WHERE alliance = ?", (alliance_id,))
                member_count = self.c_users.fetchone()[0]
                alliance_members[alliance_id] = member_count

            items_per_page = 25
            all_options = [
                discord.SelectOption(
                    label=f"{name[:40]} (ID: {alliance_id})",
                    value=f"{alliance_id}",
                    description=f"👥 Members: {alliance_members[alliance_id]} | Click to delete",
                    emoji="🗑️"
                ) for alliance_id, name in alliances
            ]
            
            option_pages = [all_options[i:i + items_per_page] for i in range(0, len(all_options), items_per_page)]
            
            embed = discord.Embed(
                title="🗑️ Delete Alliance",
                description=(
                    "**⚠️ Warning: This action cannot be undone!**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "1️⃣ Select an alliance from the dropdown menu\n"
                    "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                    f"**Current Page:** 1/{len(option_pages)}\n"
                    f"**Total Alliances:** {len(alliances)}\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.red()
            )
            embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
            embed.timestamp = discord.utils.utcnow()

            view = PaginatedDeleteView(option_pages, self.alliance_delete_callback)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            print(f"Error in delete_alliance: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while loading the delete menu.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    async def alliance_delete_callback(self, interaction: discord.Interaction):
        try:
            alliance_id = int(interaction.data["values"][0])
            
            self.c.execute("SELECT name FROM alliance_list WHERE alliance_id = ?", (alliance_id,))
            alliance_data = self.c.fetchone()
            
            if not alliance_data:
                await interaction.response.send_message("Alliance not found.", ephemeral=True)
                return
            
            alliance_name = alliance_data[0]

            self.c.execute("SELECT COUNT(*) FROM alliancesettings WHERE alliance_id = ?", (alliance_id,))
            settings_count = self.c.fetchone()[0]

            self.c_users.execute("SELECT COUNT(*) FROM users WHERE alliance = ?", (alliance_id,))
            users_count = self.c_users.fetchone()[0]

            self.c_settings.execute("SELECT COUNT(*) FROM adminserver WHERE alliances_id = ?", (alliance_id,))
            admin_server_count = self.c_settings.fetchone()[0]

            self.c_giftcode.execute("SELECT COUNT(*) FROM giftcode_channel WHERE alliance_id = ?", (alliance_id,))
            gift_channels_count = self.c_giftcode.fetchone()[0]

            self.c_giftcode.execute("SELECT COUNT(*) FROM giftcodecontrol WHERE alliance_id = ?", (alliance_id,))
            gift_code_control_count = self.c_giftcode.fetchone()[0]

            confirm_embed = discord.Embed(
                title="⚠️ Confirm Alliance Deletion",
                description=(
                    f"Are you sure you want to delete this alliance?\n\n"
                    f"**Alliance Details:**\n"
                    f"🛡️ **Name:** {alliance_name}\n"
                    f"🔢 **ID:** {alliance_id}\n"
                    f"👥 **Members:** {users_count}\n\n"
                    f"**Data to be Deleted:**\n"
                    f"⚙️ Alliance Settings: {settings_count}\n"
                    f"👥 User Records: {users_count}\n"
                    f"🏰 Admin Server Records: {admin_server_count}\n"
                    f"📢 Gift Channels: {gift_channels_count}\n"
                    f"📊 Gift Code Controls: {gift_code_control_count}\n\n"
                    "**⚠️ WARNING: This action cannot be undone!**"
                ),
                color=discord.Color.red()
            )
            
            confirm_view = discord.ui.View(timeout=60)
            
            async def confirm_callback(button_interaction: discord.Interaction):
                try:
                    self.c.execute("DELETE FROM alliance_list WHERE alliance_id = ?", (alliance_id,))
                    alliance_count = self.c.rowcount
                    
                    self.c.execute("DELETE FROM alliancesettings WHERE alliance_id = ?", (alliance_id,))
                    admin_settings_count = self.c.rowcount
                    
                    self.conn.commit()

                    self.c_users.execute("DELETE FROM users WHERE alliance = ?", (alliance_id,))
                    users_count_deleted = self.c_users.rowcount
                    self.conn_users.commit()

                    self.c_settings.execute("DELETE FROM adminserver WHERE alliances_id = ?", (alliance_id,))
                    admin_server_count = self.c_settings.rowcount
                    self.conn_settings.commit()

                    self.c_giftcode.execute("DELETE FROM giftcode_channel WHERE alliance_id = ?", (alliance_id,))
                    gift_channels_count = self.c_giftcode.rowcount

                    self.c_giftcode.execute("DELETE FROM giftcodecontrol WHERE alliance_id = ?", (alliance_id,))
                    gift_code_control_count = self.c_giftcode.rowcount
                    
                    self.conn_giftcode.commit()
                    if mongo_enabled():
                        try:
                            AlliancesAdapter.delete(alliance_id)
                            AllianceSettingsAdapter.delete(alliance_id)
                        except Exception:
                            pass

                    cleanup_embed = discord.Embed(
                        title="✅ Alliance Successfully Deleted",
                        description=(
                            f"Alliance **{alliance_name}** has been deleted.\n\n"
                            "**Cleaned Up Data:**\n"
                            f"🛡️ Alliance Records: {alliance_count}\n"
                            f"👥 Users Removed: {users_count_deleted}\n"
                            f"⚙️ Alliance Settings: {admin_settings_count}\n"
                            f"🏰 Admin Server Records: {admin_server_count}\n"
                            f"📢 Gift Channels: {gift_channels_count}\n"
                            f"📊 Gift Code Controls: {gift_code_control_count}"
                        ),
                        color=discord.Color.green()
                    )
                    cleanup_embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
                    cleanup_embed.timestamp = discord.utils.utcnow()
                    
                    await button_interaction.response.edit_message(embed=cleanup_embed, view=None)
                    
                except Exception as e:
                    error_embed = discord.Embed(
                        title="❌ Error",
                        description=f"An error occurred while deleting the alliance: {str(e)}",
                        color=discord.Color.red()
                    )
                    await button_interaction.response.edit_message(embed=error_embed, view=None)

            async def cancel_callback(button_interaction: discord.Interaction):
                cancel_embed = discord.Embed(
                    title="❌ Deletion Cancelled",
                    description="Alliance deletion has been cancelled.",
                    color=discord.Color.grey()
                )
                await button_interaction.response.edit_message(embed=cancel_embed, view=None)

            confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.danger)
            cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.grey)
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)

            await interaction.response.edit_message(embed=confirm_embed, view=confirm_view)

        except Exception as e:
            print(f"Error in alliance_delete_callback: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while processing the deletion.",
                color=discord.Color.red()
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

    async def handle_button_interaction(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        
        if custom_id == "main_menu":
            embed = discord.Embed(
                title="⚙️ Settings Menu",
                description=(
                    "Please select a category:\n\n"
                    "**Menu Categories**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏰 **Alliance Operations**\n"
                    "└ Manage alliances and settings\n\n"
                    "👥 **Alliance Member Operations**\n"
                    "└ Add, remove, and view members\n\n"
                    "🤖 **Bot Operations**\n"
                    "└ Configure bot settings\n\n"
                    "🎁 **Gift Code Operations**\n"
                    "└ Manage gift codes and rewards\n\n"
                    "📜 **Alliance History**\n"
                    "└ View alliance changes and history\n\n"
                    "🆘 **Support Operations**\n"
                    "└ Access support features\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.blue()
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Alliance Operations",
                emoji="🏰",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Member Operations",
                emoji="👥",
                style=discord.ButtonStyle.primary,
                custom_id="member_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Bot Operations",
                emoji="🤖",
                style=discord.ButtonStyle.primary,
                custom_id="bot_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Gift Operations",
                emoji="🎁",
                style=discord.ButtonStyle.primary,
                custom_id="gift_code_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Alliance History",
                emoji="📜",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_history",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Support Operations",
                emoji="🆘",
                style=discord.ButtonStyle.primary,
                custom_id="support_operations",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Other Features",
                emoji="🔧",
                style=discord.ButtonStyle.primary,
                custom_id="other_features",
                row=3
            ))


            await interaction.response.edit_message(embed=embed, view=view)

        elif custom_id == "other_features":
            try:
                other_features_cog = interaction.client.get_cog("OtherFeatures")
                if other_features_cog:
                    await other_features_cog.show_other_features_menu(interaction)
                else:
                    await interaction.response.send_message(
                        "❌ Other Features module not found.",
                        ephemeral=True
                    )
            except Exception as e:
                if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                    print(f"Other features error: {e}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred while loading Other Features menu.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "An error occurred while loading Other Features menu.",
                        ephemeral=True
                    )

    async def show_main_menu(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="⚙️ Settings Menu",
                description=(
                    "Please select a category:\n\n"
                    "**Menu Categories**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏰 **Alliance Operations**\n"
                    "└ Manage alliances and settings\n\n"
                    "👥 **Alliance Member Operations**\n"
                    "└ Add, remove, and view members\n\n"
                    "🤖 **Bot Operations**\n"
                    "└ Configure bot settings\n\n"
                    "🎁 **Gift Code Operations**\n"
                    "└ Manage gift codes and rewards\n\n"
                    "📜 **Alliance History**\n"
                    "└ View alliance changes and history\n\n"
                    "🆘 **Support Operations**\n"
                    "└ Access support features\n\n"
                    "🔧 **Other Features**\n"
                    "└ Access other features\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.blue()
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Alliance Operations",
                emoji="🏰",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Member Operations",
                emoji="👥",
                style=discord.ButtonStyle.primary,
                custom_id="member_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Bot Operations",
                emoji="🤖",
                style=discord.ButtonStyle.primary,
                custom_id="bot_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Gift Operations",
                emoji="🎁",
                style=discord.ButtonStyle.primary,
                custom_id="gift_code_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Alliance History",
                emoji="📜",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_history",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Support Operations",
                emoji="🆘",
                style=discord.ButtonStyle.primary,
                custom_id="support_operations",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Other Features",
                emoji="🔧",
                style=discord.ButtonStyle.primary,
                custom_id="other_features",
                row=3
            ))

            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except discord.InteractionResponded:
                pass
                
        except Exception as e:
            pass

    @discord.ui.button(label="Bot Operations", emoji="🤖", style=discord.ButtonStyle.primary, custom_id="bot_operations", row=1)
    async def bot_operations_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            bot_ops_cog = interaction.client.get_cog("BotOperations")
            if bot_ops_cog:
                await bot_ops_cog.show_bot_operations_menu(interaction)
            else:
                await interaction.response.send_message(
                    "❌ Bot Operations module not found.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Bot operations button error: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.",
                ephemeral=True
            )

    # =========================================================================
    # ALLIANCE MONITORING METHODS
    # =========================================================================

    def log_message(self, message: str):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)

    def _set_embed_footer(self, embed: discord.Embed, guild: Optional[discord.Guild] = None):
        """Set the standard footer for alliance monitoring embeds"""
        server_name = guild.name if guild else "ICE"
        embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
    
    def _initialize_monitoring_tables(self):
        """Create necessary database tables if they don't exist"""
        try:
            with get_db_connection('settings.sqlite') as conn:
                cursor = conn.cursor()
                
                # Alliance monitoring configuration table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS alliance_monitoring (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        alliance_id INTEGER NOT NULL,
                        channel_id INTEGER NOT NULL,
                        enabled INTEGER DEFAULT 1,
                        check_interval INTEGER DEFAULT 240,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(guild_id, alliance_id)
                    )
                """)
                
                # Member history table for change detection
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS member_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fid TEXT NOT NULL,
                        alliance_id INTEGER NOT NULL,
                        nickname TEXT NOT NULL,
                        furnace_lv INTEGER NOT NULL,
                        state_id TEXT,
                        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(fid, alliance_id)
                    )
                """)

                # New table for tracking furnace history over time
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS furnace_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fid TEXT NOT NULL,
                        nickname TEXT,
                        alliance_id INTEGER,
                        old_level INTEGER,
                        new_level INTEGER,
                        change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                self.log_message("Database tables initialized successfully")
                
                # Check if avatar_image column exists in member_history
                try:
                    cursor.execute("SELECT avatar_image FROM member_history LIMIT 1")
                except Exception:
                    try:
                        cursor.execute("ALTER TABLE member_history ADD COLUMN avatar_image TEXT")
                        conn.commit()
                        self.log_message("Added avatar_image column to member_history")
                    except Exception as e:
                        self.log_message(f"Error adding avatar_image column: {e}")
                
                # Check if state_id column exists
                try:
                    cursor.execute("SELECT state_id FROM member_history LIMIT 1")
                except Exception:
                    try:
                        cursor.execute("ALTER TABLE member_history ADD COLUMN state_id TEXT")
                        conn.commit()
                        self.log_message("Added state_id column to member_history")
                    except Exception as e:
                        self.log_message(f"Error adding state_id column: {e}")
                        
        except Exception as e:
            self.log_message(f"Error initializing database: {e}")
        except Exception as e:
            self.log_message(f"Error initializing database: {e}")

    def _sync_from_mongo(self):
        """Sync data from MongoDB to local SQLite on startup"""
        if not mongo_enabled():
            return

        self.log_message("Syncing data from MongoDB to local SQLite...")
        
        try:
            # Sync Alliance List
            alliances = AlliancesAdapter.get_all()
            for a in alliances:
                self.c.execute("INSERT OR REPLACE INTO alliance_list (alliance_id, name, discord_server_id) VALUES (?, ?, ?)",
                             (a['alliance_id'], a['name'], a['discord_server_id']))
            self.conn.commit()
            
            # Sync Alliance Settings
            settings = AllianceSettingsAdapter.get_all()
            for s in settings:
                self.c.execute("INSERT OR REPLACE INTO alliancesettings (alliance_id, channel_id, interval) VALUES (?, ?, ?)",
                             (s['alliance_id'], s['channel_id'], s['interval']))
            self.conn.commit()
            
            # Sync Alliance Monitoring
            monitors = AllianceMonitoringAdapter.get_all_monitors()
            with get_db_connection('settings.sqlite') as conn:
                cursor = conn.cursor()
                for m in monitors:
                    cursor.execute("""
                        INSERT OR REPLACE INTO alliance_monitoring 
                        (guild_id, alliance_id, channel_id, enabled, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (m['guild_id'], m['alliance_id'], m['channel_id'], m['enabled']))
                conn.commit()
                
            self.log_message(f"Synced {len(alliances)} alliances, {len(settings)} settings, {len(monitors)} monitors.")
            
        except Exception as e:
            self.log_message(f"Error syncing from MongoDB: {e}")

    def get_fl_emoji(self, fl_level: int) -> str:
        """Get emoji for furnace level"""
        # Removed custom emojis as per request
        return ""
    
    async def _get_monitoring_members(self, alliance_id: int) -> list:
        """Get all members of an alliance from database"""
        members = []
        try:
            if mongo_enabled() and AllianceMembersAdapter is not None:
                docs = await AllianceMembersAdapter.get_all_members_async() or []
                res = []
                for d in docs:
                    try:
                        if int(d.get('alliance') or d.get('alliance_id') or 0) != int(alliance_id):
                            continue
                        fid = str(d.get('fid') or d.get('id') or d.get('_id'))
                        nickname = d.get('nickname') or d.get('name') or ''
                        furnace_lv = int(d.get('furnace_lv') or d.get('furnaceLevel') or d.get('furnace', 0) or 0)
                        state_id = str(d.get('state_id') or d.get('kid') or '')
                        res.append((fid, nickname, furnace_lv, state_id))
                    except Exception:
                        continue
                if res:
                    return res
        except Exception:
            pass

        # SQLite fallback
        try:
            with get_db_connection('users.sqlite') as users_db:
                cursor = users_db.cursor()
                cursor.execute("SELECT fid, nickname, furnace_lv, kid FROM users WHERE alliance = ?", (alliance_id,))
                return cursor.fetchall()
        except Exception:
            return []
    
    async def _get_monitored_alliances(self) -> List[Dict]:
        """Get all alliances that are being monitored"""
        try:
            if mongo_enabled():
                return await AllianceMonitoringAdapter.get_all_monitors_async()
            
            with get_db_connection('settings.sqlite') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, guild_id, alliance_id, channel_id, enabled, check_interval
                    FROM alliance_monitoring
                    WHERE enabled = 1
                """)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'id': row[0],
                        'guild_id': row[1],
                        'alliance_id': row[2],
                        'channel_id': row[3],
                        'enabled': row[4],
                        'check_interval': row[5]
                    })
                return results
        except Exception as e:
            self.log_message(f"Error getting monitored alliances: {e}")
            return []
    
    async def _check_alliance_changes(self, alliance_id: int, channel_id: int, guild_id: int):
        """Check for changes in an alliance and post notifications"""
        try:
            # Get guild object for footer
            guild = self.bot.get_guild(guild_id)
            
            # Get alliance name
            alliance_name = "Unknown Alliance"
            try:
                with get_db_connection('alliance.sqlite') as alliance_db:
                    cursor = alliance_db.cursor()
                    cursor.execute("SELECT name FROM alliance_list WHERE alliance_id = ?", (alliance_id,))
                    result = cursor.fetchone()
                    if result:
                        alliance_name = result[0]
            except Exception as e:
                self.log_message(f"Error getting alliance name: {e}")
            
            # Get current members from database
            current_members = await self._get_monitoring_members(alliance_id)
            
            if not current_members:
                self.log_message(f"No members found for alliance {alliance_id}")
                return
            
            # Get channel
            channel = self.bot.get_channel(channel_id)
            if not channel:
                self.log_message(f"Channel {channel_id} not found")
                return
            
            # Extract FIDs and current states for tracking
            fids = [str(fid) for fid, _, _, *rest in current_members]
            member_map = {}
            for m in current_members:
                fid = str(m[0])
                nickname = m[1]
                furnace_lv = m[2]
                state_id = m[3] if len(m) > 3 else ''
                member_map[fid] = (nickname, furnace_lv, state_id)
            
            self.log_message(f"Fetching data for {len(fids)} members using {'dual-API' if self.login_handler.dual_api_mode else 'single-API'} mode...")
            
            # Fetch all member data concurrently using batch processing
            api_results = await self.login_handler.fetch_player_batch(
                fids,
                alliance_id=str(alliance_id)
            )
            
            # Process results and detect changes
            changes_detected = []
            successful_fetches = 0
            failed_fetches = 0
            
            for i, api_result in enumerate(api_results):
                fid = fids[i]
                current_nickname, current_furnace_lv, current_state_id = member_map[fid]
                
                if api_result['status'] == 'success':
                    successful_fetches += 1
                    api_data = api_result['data']
                    api_nickname = api_data.get('nickname', current_nickname)
                    api_furnace_lv = api_data.get('stove_lv', current_furnace_lv)
                    api_state_id = str(api_data.get('kid', current_state_id))
                    
                    # Get historical data
                    if mongo_enabled() and AllianceMembersAdapter is not None:
                        # MongoDB Logic
                        try:
                            doc = await AllianceMembersAdapter.get_member_async(str(fid)) or {}
                            
                            old_nickname = doc.get('nickname') or doc.get('name')
                            old_furnace_lv = int(doc.get('furnace_lv') or doc.get('furnaceLevel') or doc.get('furnace', 0) or 0)
                            old_avatar = doc.get('avatar_image', '')
                            
                            # Check for name change
                            if old_nickname and api_nickname != old_nickname:
                                changes_detected.append({
                                    'type': 'name_change',
                                    'fid': fid,
                                    'old_value': old_nickname,
                                    'new_value': api_nickname,
                                    'furnace_lv': api_furnace_lv,
                                    'alliance_name': alliance_name,
                                    'avatar_image': api_data.get('avatar_image', '')
                                })
                            
                            # Check for avatar change
                            api_avatar = api_data.get('avatar_image', '')
                            if api_avatar and old_avatar and api_avatar != old_avatar:
                                changes_detected.append({
                                    'type': 'avatar_change',
                                    'fid': fid,
                                    'nickname': api_nickname,
                                    'old_value': old_avatar,
                                    'new_value': api_avatar,
                                    'furnace_lv': api_furnace_lv,
                                    'alliance_name': alliance_name
                                })
                            
                            # Check for furnace level change
                            if old_furnace_lv > 0 and api_furnace_lv != old_furnace_lv:
                                changes_detected.append({
                                    'type': 'furnace_change',
                                    'fid': fid,
                                    'nickname': api_nickname,
                                    'old_value': old_furnace_lv,
                                    'new_value': api_furnace_lv,
                                    'alliance_name': alliance_name,
                                    'avatar_image': api_data.get('avatar_image', '')
                                })
                            
                            # Check for state change (Transfer)
                            old_state_id = str(doc.get('state_id') or doc.get('kid') or '')
                            if old_state_id and api_state_id != old_state_id:
                                changes_detected.append({
                                    'type': 'state_change',
                                    'fid': fid,
                                    'nickname': api_nickname,
                                    'old_value': old_state_id,
                                    'new_value': api_state_id,
                                    'furnace_lv': api_furnace_lv,
                                    'alliance_name': alliance_name,
                                    'avatar_image': api_data.get('avatar_image', '')
                                })
                            
                            # Update MongoDB document
                            doc['fid'] = str(fid)
                            doc['alliance'] = alliance_id
                            doc['nickname'] = api_nickname
                            doc['furnace_lv'] = api_furnace_lv
                            doc['state_id'] = api_state_id
                            doc['avatar_image'] = api_data.get('avatar_image', '')
                            doc['last_checked'] = datetime.utcnow()
                            
                            await AllianceMembersAdapter.upsert_member_async(str(fid), doc)
                            
                        except Exception as e:
                            self.log_message(f"Error processing MongoDB member update for {fid}: {e}")

                    else:
                        # SQLite Logic (Fallback)
                        with get_db_connection('settings.sqlite') as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                SELECT nickname, furnace_lv, avatar_image, state_id
                                FROM member_history 
                                WHERE fid = ? AND alliance_id = ?
                            """, (str(fid), alliance_id))
                            
                            history = cursor.fetchone()
                            
                            if history:
                                old_nickname = history[0]
                                old_furnace_lv = history[1]
                                
                                # Check for name change
                                if api_nickname != old_nickname:
                                    changes_detected.append({
                                        'type': 'name_change',
                                        'fid': fid,
                                        'old_value': old_nickname,
                                        'new_value': api_nickname,
                                        'furnace_lv': api_furnace_lv,
                                        'alliance_name': alliance_name,
                                        'avatar_image': api_data.get('avatar_image', '')
                                    })
                                
                                # Check for avatar change
                                api_avatar = api_data.get('avatar_image', '')
                                old_avatar = history[2] if len(history) > 2 else ''
                                
                                if api_avatar and old_avatar and api_avatar != old_avatar:
                                    changes_detected.append({
                                        'type': 'avatar_change',
                                        'fid': fid,
                                        'nickname': api_nickname,
                                        'old_value': old_avatar,
                                        'new_value': api_avatar,
                                        'furnace_lv': api_furnace_lv,
                                        'alliance_name': alliance_name
                                    })
                                
                                # Check for furnace level change
                                if api_furnace_lv != old_furnace_lv:
                                    changes_detected.append({
                                        'type': 'furnace_change',
                                        'fid': fid,
                                        'nickname': api_nickname,
                                        'old_value': old_furnace_lv,
                                        'new_value': api_furnace_lv,
                                        'alliance_name': alliance_name,
                                        'avatar_image': api_data.get('avatar_image', '')
                                    })
                                
                                # Check for state change
                                old_state_id = history[3] if len(history) > 3 and history[3] else ''
                                if old_state_id and api_state_id != old_state_id:
                                    changes_detected.append({
                                        'type': 'state_change',
                                        'fid': fid,
                                        'nickname': api_nickname,
                                        'old_value': old_state_id,
                                        'new_value': api_state_id,
                                        'furnace_lv': api_furnace_lv,
                                        'alliance_name': alliance_name,
                                        'avatar_image': api_data.get('avatar_image', '')
                                    })
                            
                            # Update or insert history
                            api_avatar = api_data.get('avatar_image', '')
                            cursor.execute("""
                                INSERT OR REPLACE INTO member_history 
                                (fid, alliance_id, nickname, furnace_lv, state_id, avatar_image, last_checked)
                                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """, (str(fid), alliance_id, api_nickname, api_furnace_lv, api_state_id, api_avatar))
                            
                            conn.commit()
                else:
                    failed_fetches += 1
                    if api_result['status'] != 'not_found':
                        self.log_message(f"Failed to fetch data for FID {fid}: {api_result.get('error_message', 'Unknown error')}")
            
            # Log batch processing results
            self.log_message(f"Batch processing complete: {successful_fetches} successful, {failed_fetches} failed out of {len(fids)} members")
            
            # Post change notifications
            for change in changes_detected:
                # Log furnace changes to history table
                if change['type'] == 'furnace_change':
                    try:
                        if mongo_enabled():
                            await FurnaceHistoryAdapter.insert_async({
                                'fid': str(change['fid']),
                                'nickname': change['nickname'],
                                'alliance_id': alliance_id,
                                'old_level': change['old_value'],
                                'new_level': change['new_value']
                            })
                        else:
                            with get_db_connection('settings.sqlite') as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT INTO furnace_history (fid, nickname, alliance_id, old_level, new_level)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (str(change['fid']), change['nickname'], alliance_id, change['old_value'], change['new_value']))
                                conn.commit()
                    except Exception as e:
                        self.log_message(f"Error logging furnace history: {e}")

                embed = self._create_change_embed(change, guild)
                await channel.send(embed=embed)
                self.log_message(f"Posted {change['type']} notification for FID {change['fid']}")
            
            if changes_detected:
                self.log_message(f"Detected {len(changes_detected)} changes for alliance {alliance_id}")
            
        except Exception as e:
            self.log_message(f"Error checking alliance {alliance_id}: {e}")
    
    def _create_change_embed(self, change: Dict, guild: Optional[discord.Guild] = None) -> discord.Embed:
        """Create an attractive embed for a detected change"""
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        if change['type'] == 'name_change':
            embed = discord.Embed(
                title="👤 Name Change Detected",
                color=discord.Color.blue()
            )
            
            furnace_level_str = self.level_mapping.get(change['furnace_lv'], str(change['furnace_lv']))
            fl_emoji = self.get_fl_emoji(change['furnace_lv'])
            
            embed.add_field(name="Player 🆔 ", value=f"`{change['fid']}`", inline=False)
            embed.add_field(name="📝 Old Name", value=f"~~`{change['old_value']}`~~", inline=True)
            embed.add_field(name="✨ New Name", value=f"**`{change['new_value']}`**", inline=True)
            embed.add_field(name="⚔️ Furnace Level", value=f"{fl_emoji} `{furnace_level_str}`", inline=False)
            embed.add_field(name="🏰 Alliance", value=f"`{change['alliance_name']}`", inline=True)
            embed.add_field(name="🕐 Time", value=f"`{timestamp}`", inline=True)
            
            if change.get('avatar_image'):
                embed.set_thumbnail(url=change['avatar_image'])
            
        elif change['type'] == 'avatar_change':
            embed = discord.Embed(
                title="<a:profile:1454933848516464891> Avatar Change Detected",
                color=discord.Color.purple()
            )
            
            furnace_level_str = self.level_mapping.get(change['furnace_lv'], str(change['furnace_lv']))
            fl_emoji = self.get_fl_emoji(change['furnace_lv'])
            
            embed.add_field(name="🆔 Player ID", value=f"`{change['fid']}`", inline=False)
            embed.add_field(name="👤 Player Name", value=f"`{change['nickname']}`", inline=False)
            embed.add_field(name="⚔️ Furnace Level", value=f"{fl_emoji} `{furnace_level_str}`", inline=False)
            embed.add_field(name="🏰 Alliance", value=f"`{change['alliance_name']}`", inline=True)
            embed.add_field(name="🕐 Time", value=f"`{timestamp}`", inline=True)
            embed.add_field(name="Previous Profile ↗️", value="*(See Thumbnail)*", inline=True)
            
            embed.add_field(name="New Profile ⬇️", value="*(See Image Below)*", inline=False)
            
            # Set old avatar as thumbnail and new avatar as image
            if change['old_value']:
                embed.set_thumbnail(url=change['old_value'])
            
            if change['new_value']:
                embed.set_image(url=change['new_value'])
            
        elif change['type'] == 'furnace_change':
            # Determine if it's an upgrade or downgrade
            is_upgrade = change['new_value'] > change['old_value']
            title = "<a:furnace:1454930497623953591> Furnace Level Up 📈" if is_upgrade else "📉 Furnace Level Change"
            color = discord.Color.green() if is_upgrade else discord.Color.orange()
            
            embed = discord.Embed(
                title=title,
                color=color
            )
            
            old_level_str = self.level_mapping.get(change['old_value'], str(change['old_value']))
            new_level_str = self.level_mapping.get(change['new_value'], str(change['new_value']))
            old_emoji = self.get_fl_emoji(change['old_value'])
            new_emoji = self.get_fl_emoji(change['new_value'])
            
            embed.add_field(name="Player 🆔", value=f"`{change['fid']}`", inline=False)
            embed.add_field(name="👤 Player Name", value=f"`{change['nickname']}`", inline=False)
            embed.add_field(name="📊 Previous Level", value=f"{old_emoji} `{old_level_str}`", inline=True)
            embed.add_field(name="🎉 New Level", value=f"{new_emoji} `{new_level_str}`", inline=True)
            embed.add_field(name="🏰 Alliance", value=f"`{change['alliance_name']}`", inline=True)
            embed.add_field(name="🕐 Time", value=f"`{timestamp}`", inline=True)
            
            if change.get('avatar_image'):
                embed.set_thumbnail(url=change['avatar_image'])
        
        elif change['type'] == 'state_change':
            embed = discord.Embed(
                title="✈️ State Transfer Detected",
                description=f"**{change['nickname']}** has transferred to a different state!",
                color=discord.Color.gold()
            )
            
            furnace_level_str = self.level_mapping.get(change['furnace_lv'], str(change['furnace_lv']))
            fl_emoji = self.get_fl_emoji(change['furnace_lv'])
            
            embed.add_field(name="Player 🆔", value=f"`{change['fid']}`", inline=False)
            embed.add_field(name="👤 Player Name", value=f"`{change['nickname']}`", inline=False)
            embed.add_field(name="🌍 Old State", value=f"`#{change['old_value']}`", inline=True)
            embed.add_field(name="🚀 New State", value=f"**`#{change['new_value']}`**", inline=True)
            embed.add_field(name="⚔️ Furnace Level", value=f"{fl_emoji} `{furnace_level_str}`", inline=False)
            embed.add_field(name="🏰 Alliance", value=f"`{change['alliance_name']}`", inline=True)
            embed.add_field(name="🕐 Time", value=f"`{timestamp}`", inline=True)
            
            if change.get('avatar_image'):
                embed.set_thumbnail(url=change['avatar_image'])
        
        self._set_embed_footer(embed, guild)
        return embed
    
    @tasks.loop(minutes=4)
    async def monitor_alliances(self):
        """Background task that monitors alliances for changes"""
        try:
            self.log_message("Starting alliance monitoring cycle")
            
            monitored = await self._get_monitored_alliances()
            
            if not monitored:
                self.log_message("No alliances being monitored")
                return
            
            self.log_message(f"Monitoring {len(monitored)} alliance(s)")
            
            for config in monitored:
                await self._check_alliance_changes(
                    config['alliance_id'],
                    config['channel_id'],
                    config['guild_id']
                )
                
                # Add delay between alliances
                await asyncio.sleep(5)
            
            self.log_message("Alliance monitoring cycle completed")
            
        except Exception as e:
            self.log_message(f"Error in monitoring task: {e}")
    
    @monitor_alliances.before_loop
    async def before_monitor_alliances(self):
        """Wait for bot to be ready before starting monitoring"""
        await self.bot.wait_until_ready()
        
        # Check API availability and enable dual-API mode if not already done
        if not self._api_check_done:
            try:
                self.log_message("Checking API availability for dual-API mode...")
                api_status = await self.login_handler.check_apis_availability()
                
                if self.login_handler.dual_api_mode:
                    self.log_message(f"✓ Dual API mode enabled with APIs {self.login_handler.available_apis}")
                    self.log_message(f"  API 1: {api_status['api1_url']} - {'Available' if api_status['api1_available'] else 'Unavailable'}")
                    self.log_message(f"  API 2: {api_status['api2_url']} - {'Available' if api_status['api2_available'] else 'Unavailable'}")
                    self.log_message(f"  Request delay: {self.login_handler.request_delay}s (concurrent processing enabled)")
                else:
                    self.log_message(f"Single API mode - using API {self.login_handler.available_apis[0] if self.login_handler.available_apis else 'None'}")
                    self.log_message(f"  Request delay: {self.login_handler.request_delay}s")
                
                self._api_check_done = True
            except Exception as e:
                self.log_message(f"Error checking API availability: {e}")
        
        self.log_message("Alliance monitoring task ready")
    
    # /setalliancelogchannel command removed - now available via /alliancemonitor dashboard
    
    # /selectalliance command removed - now available via /alliancemonitor dashboard
    
    # /alliancemonitoringstatus command removed - now available via /alliancemonitor dashboard
    
    @app_commands.command(name="alliancemonitor", description="Alliance monitoring dashboard with quick access to all monitoring features")
    @command_animation
    async def alliance_monitor(self, interaction: discord.Interaction):
        """Display alliance monitoring dashboard with authentication"""
        try:
            # Import authentication adapters
            from db.mongo_adapters import mongo_enabled, ServerAllianceAdapter, AuthSessionsAdapter
            
            # Check if MongoDB is enabled
            if not mongo_enabled() or not ServerAllianceAdapter:
                await interaction.followup.send(
                    "❌ MongoDB not enabled. Cannot access Alliance Monitor.",
                    ephemeral=True
                )
                return
            
            # Check if password is set
            stored_password = ServerAllianceAdapter.get_password(interaction.guild.id)
            if not stored_password:
                error_embed = discord.Embed(
                    title="🔒 Access Denied",
                    description="No password configured for Alliance Monitor access.",
                    color=0x2B2D31
                )
                error_embed.add_field(
                    name="⚙️ Administrator Action Required",
                    value="Contact a server administrator to set up password via:\n`/settings` → **Bot Operations** → **Set Member List Password**",
                    inline=False
                )
                error_embed.add_field(
                    name="💬 Need Help?",
                    value="Contact the Global Admin for assistance with bot setup.",
                    inline=False
                )
                
                # Create view with contact button
                class ContactAdminView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=None)
                        # Add link button to contact global admin
                        self.add_item(discord.ui.Button(
                            label="Contact Global Admin",
                            emoji="👤",
                            style=discord.ButtonStyle.link,
                            url="https://discord.com/users/850786361572720661"
                        ))
                
                view = ContactAdminView()
                await interaction.followup.send(embed=error_embed, view=view, ephemeral=True)
                return
            
            # Check if user has a valid authentication session
            if AuthSessionsAdapter and AuthSessionsAdapter.is_session_valid(
                interaction.guild.id,
                interaction.user.id,
                stored_password
            ):
                # User has valid session, show Alliance Monitor dashboard directly
                view = AllianceMonitorView(self, interaction.guild.id)
                
                embed = discord.Embed(
                    title="🏰 Alliance Monitoring Dashboard",
                    description=(
                        "Centralized control panel for alliance monitoring operations.\n\n"
                        "**Available Features:**\n"
                        "• 👤 Track name changes\n"
                        "• 🔥 Monitor furnace level changes\n"
                        "• 🖼️ Detect avatar changes\n\n"
                        "Use the buttons below to manage your monitoring settings."
                    ),
                    color=discord.Color.blue()
                )
                await interaction.followup.send(
                    content="✅ **Access Granted** (Session Active)",
                    embed=embed,
                    view=view,
                    ephemeral=True
                )
                return
            
            # No valid session - show authentication modal
            class AllianceAuthModal(discord.ui.Modal, title="🛡️ Security Verification"):
                password_input = discord.ui.TextInput(
                    label="Enter Access Code",
                    placeholder="••••••••••••",
                    style=discord.TextStyle.short,
                    required=True,
                    max_length=50
                )
                
                def __init__(self, guild_id: int, guild_name: str, cog_instance):
                    super().__init__()
                    self.guild_id = guild_id
                    self.guild_name = guild_name
                    self.cog = cog_instance
                
                async def on_submit(self, modal_interaction: discord.Interaction):
                    try:
                        entered_password = self.password_input.value.strip()
                        
                        # Verify password
                        if not ServerAllianceAdapter.verify_password(self.guild_id, entered_password):
                            error_embed = discord.Embed(
                                title="❌ Authentication Failed",
                                description="The access code you entered is incorrect.",
                                color=0xED4245
                            )
                            error_embed.add_field(
                                name="🔄 Try Again",
                                value="Use `/alliancemonitor` command again to retry.",
                                inline=False
                            )
                            await modal_interaction.response.send_message(embed=error_embed, ephemeral=True)
                            return
                        
                        # Authentication successful - create session
                        if AuthSessionsAdapter:
                            try:
                                AuthSessionsAdapter.create_session(
                                    self.guild_id,
                                    modal_interaction.user.id,
                                    entered_password
                                )
                            except Exception as session_error:
                                print(f"Failed to create auth session: {session_error}")
                        
                        # Show Alliance Monitor dashboard directly
                        view = AllianceMonitorView(self.cog, modal_interaction.guild.id)
                        
                        embed = discord.Embed(
                            title="🏰 Alliance Monitoring Dashboard",
                            description=(
                                "Centralized control panel for alliance monitoring operations.\n\n"
                                "**Available Features:**\n"
                                "• 👤 Track name changes\n"
                                "• 🔥 Monitor furnace level changes\n"
                                "• 🖼️ Detect avatar changes\n\n"
                                "Use the buttons below to manage your monitoring settings."
                            ),
                            color=discord.Color.blue()
                        )
                        await modal_interaction.response.send_message(
                            content="✅ **Access Granted**",
                            embed=embed,
                            view=view,
                            ephemeral=True
                        )
                    
                    except Exception as e:
                        print(f"Error in alliance auth modal: {e}")
                        import traceback
                        traceback.print_exc()
                        await modal_interaction.response.send_message(
                            "❌ An error occurred during authentication.",
                            ephemeral=True
                        )
            
            # Create authentication view with button
            class AllianceAuthView(discord.ui.View):
                def __init__(self, guild_id: int, guild_name: str, cog_instance):
                    super().__init__(timeout=60)
                    self.guild_id = guild_id
                    self.guild_name = guild_name
                    self.cog = cog_instance
                
                @discord.ui.button(label="Authenticate", emoji="🔐", style=discord.ButtonStyle.secondary, custom_id="alliance_auth_cmd")
                async def authenticate(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    modal = AllianceAuthModal(self.guild_id, self.guild_name, self.cog)
                    await button_interaction.response.send_modal(modal)
            
            # Create authentication embed
            auth_embed = discord.Embed(
                title=interaction.guild.name,
                description="**Alliance Monitor Access**\n\nAuthentication required to access alliance monitoring features.",
                color=0x2B2D31
            )
            
            auth_embed.set_author(
                name="SECURITY VERIFICATION REQUIRED",
                icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445470757844160543/unnamed_6_1.png"
            )
            
            auth_embed.add_field(
                name="🔒 Protected Resource",
                value="Alliance Monitoring Dashboard",
                inline=True
            )
            
            auth_embed.add_field(
                name="🔑 Authentication Method",
                value="Access Code",
                inline=True
            )
            
            auth_embed.add_field(
                name="⚡ Quick Actions",
                value="Click the button below to proceed with authentication.",
                inline=False
            )
            
            auth_embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
            
            # Send authentication embed with button
            view = AllianceAuthView(interaction.guild.id, interaction.guild.name, self)
            await interaction.followup.send(embed=auth_embed, view=view, ephemeral=True)
            
        except Exception as e:
            self.log_message(f"Error in alliance_monitor: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                "❌ An error occurred while opening the monitoring dashboard.",
                ephemeral=True
            )
    
    @app_commands.command(name="allianceactivity", description="Show player growth based on furnace changes (Last 7 Days)")
    @command_animation
    async def alliance_activity(self, interaction: discord.Interaction):
        """Show player growth based on furnace changes over the last 7 days"""
        try:
            # Check admin permissions
            admin_info = self._get_admin(interaction.user.id)
            if not admin_info:
                await interaction.followup.send(
                    "❌ You don't have permission to use this command.",
                    ephemeral=True
                )
                return

            # Get server's assigned alliance
            try:
                from db.mongo_adapters import ServerAllianceAdapter
            except:
                await interaction.followup.send(
                    "❌ MongoDB not enabled. Alliance activity requires MongoDB.",
                    ephemeral=True
                )
                return
            
            alliance_id = ServerAllianceAdapter.get_alliance(interaction.guild_id)
            
            if not alliance_id:
                await interaction.followup.send(
                    "❌ **No Alliance Assigned**\\n\\n"
                    "This server doesn't have an assigned alliance yet.\\n\\n"
                    "**To assign an alliance:**\\n"
                    "1. Use `/manage` command\\n"
                    "2. Click **Assign Server Alliance**\\n"
                    "3. Select your alliance\\n\\n"
                    "Then return here to view alliance activity.",
                    ephemeral=True
                )
                return
            
            # Get alliance name
            alliance_name = f"Alliance {alliance_id}"
            try:
                with get_db_connection('alliance.sqlite') as alliance_db:
                    cursor = alliance_db.cursor()
                    cursor.execute("SELECT name FROM alliance_list WHERE alliance_id = ?", (alliance_id,))
                    result = cursor.fetchone()
                    if result:
                        alliance_name = result[0]
            except Exception:
                pass
            
            # Query comprehensive activity data
            results = []
            if mongo_enabled():
                results = FurnaceHistoryAdapter.get_recent_changes(days=7, alliance_id=alliance_id)
            else:
                with get_db_connection('settings.sqlite') as conn:
                    cursor = conn.cursor()
                    # Get comprehensive activity data from last 7 days
                    cursor.execute("""
                        SELECT 
                            fh.fid,
                            mh.nickname,
                            SUM(fh.new_level - fh.old_level) as furnace_growth,
                            COUNT(DISTINCT fh.id) as furnace_changes,
                            MAX(fh.change_date) as last_activity
                        FROM furnace_history fh
                        LEFT JOIN member_history mh ON fh.fid = mh.fid AND fh.alliance_id = mh.alliance_id
                        WHERE fh.change_date >= datetime('now', '-7 days')
                            AND fh.alliance_id = ?
                        GROUP BY fh.fid
                        HAVING furnace_growth > 0
                        ORDER BY furnace_growth DESC, last_activity DESC
                    """, (alliance_id,))
                    results = cursor.fetchall()

            if not results:
                await interaction.followup.send(
                    f"📊 **No Player Activity**\\n\\n"
                    f"No furnace level changes recorded for **{alliance_name}** in the last 7 days.",
                    ephemeral=True
                )
                return

            # Pagination Logic
            items_per_page = 10
            pages = [results[i:i + items_per_page] for i in range(0, len(results), items_per_page)]

            class PaginatedActivityView(discord.ui.View):
                def __init__(self, pages, cog_ref, alliance_name):
                    super().__init__(timeout=300)
                    self.pages = pages
                    self.current_page = 0
                    self.cog = cog_ref
                    self.alliance_name = alliance_name
                    self.update_buttons()

                def update_buttons(self):
                    self.prev_button.disabled = self.current_page == 0
                    self.next_button.disabled = self.current_page == len(self.pages) - 1
                    self.page_counter.label = f"Page {self.current_page + 1}/{len(self.pages)}"

                def get_embed(self):
                    from datetime import datetime, timedelta
                    page_data = self.pages[self.current_page]
                    description = ""
                    
                    for i, item in enumerate(page_data, 1):
                        # Handle both dictionary (MongoDB) and tuple (SQLite) results
                        if isinstance(item, dict):
                            fid = item['_id']
                            nickname = item.get('nickname', 'Unknown')
                            growth = item['total_growth']
                            changes = item.get('change_count', 1)
                            last_activity = item.get('last_activity')
                        else:
                            fid = item[0]
                            nickname = item[1] if item[1] else 'Unknown'
                            growth = item[2]
                            changes = item[3] if len(item) > 3 else 1
                            last_activity = item[4] if len(item) > 4 else None
                        
                        rank = (self.current_page * items_per_page) + i
                        
                        # Format player info
                        description += f"**{rank}. {nickname}**\\n"
                        description += f"└ ID: `{fid}`\\n"
                        description += f"└ 📈 Furnace Growth: **+{growth}** levels\\n"
                        description += f"└ 🔥 Changes: **{changes}** times\\n"
                        
                        # Format last activity timestamp
                        if last_activity:
                            try:
                                if isinstance(last_activity, str):
                                    activity_time = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                                else:
                                    activity_time = last_activity
                                
                                time_diff = datetime.utcnow() - activity_time.replace(tzinfo=None)
                                
                                if time_diff < timedelta(hours=1):
                                    minutes = int(time_diff.total_seconds() / 60)
                                    time_str = f"{minutes} min ago" if minutes > 0 else "Just now"
                                elif time_diff < timedelta(days=1):
                                    hours = int(time_diff.total_seconds() / 3600)
                                    time_str = f"{hours} hour{'s' if hours != 1 else ''} ago"
                                else:
                                    days = time_diff.days
                                    time_str = f"{days} day{'s' if days != 1 else ''} ago"
                                
                                description += f"└ 📅 Last Active: {time_str}\\n"
                            except:
                                pass
                        
                        description += "\\n"
                    
                    embed = discord.Embed(
                        title=f"🔥 {self.alliance_name} - Activity Report",
                        description=description,
                        color=discord.Color.gold()
                    )
                    embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
                    
                    # Set embed footer with bot branding
                    self.cog._set_embed_footer(embed)
                    
                    return embed

                @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, row=0)
                async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.current_page -= 1
                    self.update_buttons()
                    await interaction.response.edit_message(embed=self.get_embed(), view=self)

                @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
                async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
                    pass

                @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, row=0)
                async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.current_page += 1
                    self.update_buttons()
                    await interaction.response.edit_message(embed=self.get_embed(), view=self)

            view = PaginatedActivityView(pages, self, alliance_name)
            await interaction.followup.send(embed=view.get_embed(), view=view, ephemeral=True)

        except Exception as e:
            print(f"Error in alliance_activity: {e}")
            try:
                await interaction.followup.send("❌ An error occurred.", ephemeral=True)
            except:
                pass

    # /stopalliancemonitoring command removed - now available via /alliancemonitor dashboard

class AllianceMonitorView(discord.ui.View):
    """Interactive view for alliance monitoring dashboard"""
    def __init__(self, cog, guild_id=None):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.guild_id = guild_id
        
        # Dynamically update the toggle button based on monitoring status
        if guild_id:
            self._update_toggle_button()
    
    def _update_toggle_button(self):
        """Update the toggle button based on current monitoring status"""
        try:
            # Import ServerAllianceAdapter
            from db.mongo_adapters import ServerAllianceAdapter
            
            # Get server's assigned alliance
            alliance_id = ServerAllianceAdapter.get_alliance(self.guild_id)
            
            if alliance_id:
                # Check if monitoring is enabled
                with get_db_connection('settings.sqlite') as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT enabled
                        FROM alliance_monitoring
                        WHERE guild_id = ? AND alliance_id = ?
                    """, (self.guild_id, alliance_id))
                    
                    result = cursor.fetchone()
                    is_enabled = result[0] if result else False
                
                # Find and update the toggle button
                for item in self.children:
                    if isinstance(item, discord.ui.Button) and item.custom_id == "toggle_monitoring":
                        if is_enabled:
                            item.label = "Stop Monitoring"
                            item.emoji = "🛑"
                            item.style = discord.ButtonStyle.danger
                        else:
                            item.label = "Enable Monitoring"
                            item.emoji = "✅"
                            item.style = discord.ButtonStyle.success
                        break
        except Exception as e:
            self.cog.log_message(f"Error updating toggle button: {e}")
    
    @discord.ui.button(
        label="Set Log Channel",
        emoji="📝",
        style=discord.ButtonStyle.primary,
        custom_id="set_log_channel"
    )
    async def set_log_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to set alliance log channel - automatically uses server's assigned alliance"""
        try:
            # Import ServerAllianceAdapter
            try:
                from db.mongo_adapters import ServerAllianceAdapter
            except:
                await interaction.response.send_message(
                    "❌ MongoDB not enabled. Alliance monitoring requires MongoDB.",
                    ephemeral=True
                )
                return
            
            # Get server's assigned alliance
            alliance_id = ServerAllianceAdapter.get_alliance(interaction.guild_id)
            
            if not alliance_id:
                await interaction.response.send_message(
                    "❌ **No Alliance Assigned**\n\n"
                    "This server doesn't have an assigned alliance yet.\n\n"
                    "**To assign an alliance:**\n"
                    "1. Use `/manage` command\n"
                    "2. Click **Assign Server Alliance**\n"
                    "3. Select your alliance\n\n"
                    "Then return here to set up monitoring.",
                    ephemeral=True
                )
                return
            
            # Get alliance name
            alliance_name = "Unknown Alliance"
            try:
                with get_db_connection('alliance.sqlite') as alliance_db:
                    cursor = alliance_db.cursor()
                    cursor.execute("SELECT name FROM alliance_list WHERE alliance_id = ?", (alliance_id,))
                    result = cursor.fetchone()
                    if result:
                        alliance_name = result[0]
            except Exception:
                pass
            
            # Check if monitoring is already configured
            current_channel_id = None
            is_enabled = False
            try:
                with get_db_connection('settings.sqlite') as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT channel_id, enabled 
                        FROM alliance_monitoring 
                        WHERE guild_id = ? AND alliance_id = ?
                    """, (interaction.guild_id, alliance_id))
                    result = cursor.fetchone()
                    if result:
                        current_channel_id = result[0]
                        is_enabled = result[1]
            except Exception:
                pass
            
            # Create channel select menu
            channel_select = discord.ui.ChannelSelect(
                placeholder="Select a channel for alliance logs...",
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1
            )
            
            async def channel_callback(select_interaction: discord.Interaction):
                channel = select_interaction.data['values'][0]
                channel_id = int(channel)
                
                # Save monitoring configuration immediately
                try:
                    # Get member count
                    members = await self.cog._get_monitoring_members(alliance_id)
                    member_count = len(members) if members else 0
                    
                    # Save to database
                    with get_db_connection('settings.sqlite') as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT OR REPLACE INTO alliance_monitoring 
                            (guild_id, alliance_id, channel_id, enabled, updated_at)
                            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                        """, (interaction.guild_id, alliance_id, channel_id))
                        conn.commit()
                    
                    # Save to MongoDB
                    if mongo_enabled():
                        AllianceMonitoringAdapter.upsert_monitor(interaction.guild_id, alliance_id, channel_id, enabled=1)
                    
                    # Initialize member history
                    if members:
                        with get_db_connection('settings.sqlite') as conn:
                            cursor = conn.cursor()
                            for fid, nickname, furnace_lv, *_ in members:
                                cursor.execute("""
                                    INSERT OR REPLACE INTO member_history 
                                    (fid, alliance_id, nickname, furnace_lv, last_checked)
                                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                                """, (str(fid), alliance_id, nickname, furnace_lv))
                            conn.commit()
                    
                    # Create success embed
                    success_embed = discord.Embed(
                        title="✅ Alliance Monitoring Configured",
                        description=(
                            f"**Alliance:** {alliance_name}\n"
                            f"**Alliance ID:** {alliance_id}\n"
                            f"**Log Channel:** <#{channel_id}>\n"
                            f"**Members Tracked:** {member_count}\n\n"
                            f"**Monitoring Active** ✅\n"
                            f"The system will check for changes every 4 minutes.\n\n"
                            f"**Tracked Changes:**\n"
                            f"• 👤 Name changes\n"
                            f"• 🔥 Furnace level changes\n"
                            f"• 🖼️ Avatar changes"
                        ),
                        color=discord.Color.green()
                    )
                    
                    self.cog._set_embed_footer(success_embed)
                    
                    await select_interaction.response.edit_message(
                        content=None,
                        embed=success_embed,
                        view=None
                    )
                    
                    self.cog.log_message(f"Monitoring configured for alliance {alliance_id} ({alliance_name}) in channel {channel_id}")
                    
                except Exception as e:
                    self.cog.log_message(f"Error saving monitoring config: {e}")
                    await select_interaction.response.edit_message(
                        content="❌ Error saving monitoring configuration.",
                        embed=None,
                        view=None
                    )
            
            channel_select.callback = channel_callback
            view = discord.ui.View()
            view.add_item(channel_select)
            
            # Create message with current status
            status_msg = f"**Alliance:** {alliance_name} (ID: {alliance_id})\n\n"
            
            if current_channel_id:
                status_emoji = "✅" if is_enabled else "⚠️"
                status_text = "Active" if is_enabled else "Disabled"
                status_msg += (
                    f"**Current Status:** {status_emoji} {status_text}\n"
                    f"**Current Channel:** <#{current_channel_id}>\n\n"
                    f"Select a new channel below to change the monitoring channel:"
                )
            else:
                status_msg += "Select a channel below to start monitoring this alliance:"
            
            await interaction.response.send_message(
                status_msg,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            self.cog.log_message(f"Error in set_log_channel_button: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while setting the log channel.",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="View Status",
        emoji="📊",
        style=discord.ButtonStyle.secondary,
        custom_id="view_status"
    )
    async def view_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to view monitoring status for server's assigned alliance"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Import ServerAllianceAdapter
            try:
                from db.mongo_adapters import ServerAllianceAdapter
            except:
                await interaction.followup.send(
                    "❌ MongoDB not enabled. Alliance monitoring requires MongoDB.",
                    ephemeral=True
                )
                return
            
            # Get server's assigned alliance
            alliance_id = ServerAllianceAdapter.get_alliance(interaction.guild_id)
            
            if not alliance_id:
                await interaction.followup.send(
                    "ℹ️ **No Alliance Assigned**\n\n"
                    "This server doesn't have an assigned alliance yet.\n\n"
                    "Use `/manage` → **Assign Server Alliance** to assign one.",
                    ephemeral=True
                )
                return
            
            # Get monitoring configuration for the assigned alliance
            with get_db_connection('settings.sqlite') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT channel_id, enabled, created_at, updated_at
                    FROM alliance_monitoring
                    WHERE guild_id = ? AND alliance_id = ?
                """, (interaction.guild_id, alliance_id))
                
                config = cursor.fetchone()
            
            # Get alliance name
            alliance_name = "Unknown Alliance"
            member_count = 0
            try:
                with get_db_connection('alliance.sqlite') as alliance_db:
                    cursor = alliance_db.cursor()
                    cursor.execute("SELECT name FROM alliance_list WHERE alliance_id = ?", (alliance_id,))
                    result = cursor.fetchone()
                    if result:
                        alliance_name = result[0]
                
                # Get member count from history
                with get_db_connection('settings.sqlite') as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT COUNT(*) FROM member_history WHERE alliance_id = ?
                    """, (alliance_id,))
                    member_count = cursor.fetchone()[0]
            except Exception:
                pass
            
            # Create status embed
            if not config:
                embed = discord.Embed(
                    title="📊 Alliance Monitoring Status",
                    description=(
                        f"**Server Alliance:** {alliance_name}\n"
                        f"**Alliance ID:** {alliance_id}\n\n"
                        f"**Status:** ⚠️ Not Configured\n\n"
                        f"Use the **Set Log Channel** button to start monitoring this alliance."
                    ),
                    color=discord.Color.orange()
                )
            else:
                channel_id, enabled, created_at, updated_at = config
                status_emoji = "✅" if enabled else "❌"
                status_text = "Active" if enabled else "Disabled"
                
                embed = discord.Embed(
                    title="📊 Alliance Monitoring Status",
                    description=(
                        f"**Server Alliance:** {alliance_name}\n"
                        f"**Alliance ID:** {alliance_id}\n\n"
                        f"**Status:** {status_emoji} {status_text}\n"
                        f"**Log Channel:** <#{channel_id}>\n"
                        f"**Members Tracked:** {member_count}\n\n"
                        f"**Monitored Changes:**\n"
                        f"• 👤 Name changes\n"
                        f"• 🔥 Furnace level changes\n"
                        f"• 🖼️ Avatar changes\n\n"
                        f"The system checks for changes every 4 minutes."
                    ),
                    color=discord.Color.green() if enabled else discord.Color.red()
                )
            
            self.cog._set_embed_footer(embed, interaction.guild)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.cog.log_message(f"Error in view_status_button: {e}")
            await interaction.followup.send(
                "❌ An error occurred while retrieving monitoring status.",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="Stop Monitoring",
        emoji="🛑",
        style=discord.ButtonStyle.danger,
        custom_id="toggle_monitoring"
    )
    async def toggle_monitoring_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to toggle monitoring (enable/disable) for the server's assigned alliance"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Import ServerAllianceAdapter
            try:
                from db.mongo_adapters import ServerAllianceAdapter
            except:
                await interaction.followup.send(
                    "❌ MongoDB not enabled. Alliance monitoring requires MongoDB.",
                    ephemeral=True
                )
                return
            
            # Get server's assigned alliance
            alliance_id = ServerAllianceAdapter.get_alliance(interaction.guild_id)
            
            if not alliance_id:
                await interaction.followup.send(
                    "ℹ️ **No Alliance Assigned**\n\n"
                    "This server doesn't have an assigned alliance.",
                    ephemeral=True
                )
                return
            
            # Check current monitoring status
            with get_db_connection('settings.sqlite') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT channel_id, enabled
                    FROM alliance_monitoring
                    WHERE guild_id = ? AND alliance_id = ?
                """, (interaction.guild_id, alliance_id))
                
                result = cursor.fetchone()
            
            if not result:
                await interaction.followup.send(
                    "ℹ️ **Monitoring Not Configured**\n\n"
                    "Please use **Set Log Channel** first to configure monitoring.",
                    ephemeral=True
                )
                return
            
            channel_id, is_enabled = result
            
            # Get alliance name
            alliance_name = "Unknown Alliance"
            try:
                with get_db_connection('alliance.sqlite') as alliance_db:
                    cursor = alliance_db.cursor()
                    cursor.execute("SELECT name FROM alliance_list WHERE alliance_id = ?", (alliance_id,))
                    result = cursor.fetchone()
                    if result:
                        alliance_name = result[0]
            except Exception:
                pass
            
            # Toggle monitoring status
            new_status = 0 if is_enabled else 1
            
            try:
                with get_db_connection('settings.sqlite') as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE alliance_monitoring 
                        SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND alliance_id = ?
                    """, (new_status, interaction.guild_id, alliance_id))
                    conn.commit()

                if mongo_enabled():
                    AllianceMonitoringAdapter.upsert_monitor(interaction.guild_id, alliance_id, channel_id, enabled=new_status)
                
                # Create appropriate embed based on new status
                if new_status == 1:
                    # Get member count
                    members = await self.cog._get_monitoring_members(alliance_id)
                    member_count = len(members) if members else 0
                    
                    success_embed = discord.Embed(
                        title="✅ Alliance Monitoring Enabled",
                        description=(
                            f"**Alliance:** {alliance_name}\n"
                            f"**Alliance ID:** {alliance_id}\n"
                            f"**Log Channel:** <#{channel_id}>\n"
                            f"**Members Tracked:** {member_count}\n\n"
                            f"**Monitoring Active** ✅\n"
                            f"The system will check for changes every 4 minutes.\n\n"
                            f"**Tracked Changes:**\n"
                            f"• 👤 Name changes\n"
                            f"• 🔥 Furnace level changes\n"
                            f"• 🖼️ Avatar changes"
                        ),
                        color=discord.Color.green()
                    )
                    action_msg = "enabled"
                else:
                    success_embed = discord.Embed(
                        title="🛑 Alliance Monitoring Stopped",
                        description=(
                            f"**Alliance:** {alliance_name}\n"
                            f"**Alliance ID:** {alliance_id}\n\n"
                            f"Monitoring has been disabled.\n"
                            f"Member history has been preserved.\n\n"
                            f"Click **Enable Monitoring** to re-enable monitoring."
                        ),
                        color=discord.Color.red()
                    )
                    action_msg = "stopped"
                
                self.cog._set_embed_footer(success_embed)
                
                # Update the button in the view
                if new_status == 1:
                    button.label = "Stop Monitoring"
                    button.emoji = "🛑"
                    button.style = discord.ButtonStyle.danger
                else:
                    button.label = "Enable Monitoring"
                    button.emoji = "✅"
                    button.style = discord.ButtonStyle.success
                
                # Send the response with updated view
                await interaction.followup.send(embed=success_embed, ephemeral=True)
                
                # Update the original message with the new button state
                try:
                    # Get the original message from the interaction
                    original_message = await interaction.original_response()
                    if original_message:
                        # Update the view with new button state
                        await original_message.edit(view=self)
                except:
                    pass
                
                self.cog.log_message(f"Monitoring {action_msg} for alliance {alliance_id} ({alliance_name})")
                
            except Exception as e:
                self.cog.log_message(f"Error toggling monitoring: {e}")
                await interaction.followup.send(
                    "❌ An error occurred while toggling monitoring.",
                    ephemeral=True
                )
            
        except Exception as e:
            self.cog.log_message(f"Error in toggle_monitoring_button: {e}")
            await interaction.followup.send(
                "❌ An error occurred.",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="Back",
        emoji="◀️",
        style=discord.ButtonStyle.secondary,
        custom_id="alliance_monitor_back",
        row=2
    )
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to previous menu"""
        try:
            await interaction.response.edit_message(
                content="✅ Closed Alliance Monitor",
                embed=None,
                view=None
            )
        except Exception as e:
            self.cog.log_message(f"Error in back_button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred.",
                    ephemeral=True
                )

class AllianceModal(discord.ui.Modal):
    def __init__(self, title: str, default_name: str = "", default_interval: str = "0"):
        super().__init__(title=title)
        
        self.name = discord.ui.TextInput(
            label="Alliance Name",
            placeholder="Enter alliance name",
            default=default_name,
            required=True
        )
        self.add_item(self.name)
        
        self.interval = discord.ui.TextInput(
            label="Control Interval (minutes)",
            placeholder="Enter interval (0 to disable)",
            default=default_interval,
            required=True
        )
        self.add_item(self.interval)

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction

class AllianceView(discord.ui.View):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    @discord.ui.button(
        label="Main Menu",
        emoji="🏠",
        style=discord.ButtonStyle.secondary,
        custom_id="main_menu"
    )
    async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_main_menu(interaction)

class MemberOperationsView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def get_admin_alliances(self, user_id, guild_id):
        self.cog.c_settings.execute("SELECT id, is_initial FROM admin WHERE id = ?", (user_id,))
        admin = self.cog.c_settings.fetchone()
        
        if admin is None:
            return []
            
        is_initial = admin[1]
        
        if is_initial == 1:
            self.cog.c.execute("SELECT alliance_id, name FROM alliance_list ORDER BY name")
        else:
            self.cog.c.execute("""
                SELECT alliance_id, name 
                FROM alliance_list 
                WHERE discord_server_id = ? 
                ORDER BY name
            """, (guild_id,))
            
        return self.cog.c.fetchall()

    @discord.ui.button(label="Add Member", emoji="➕", style=discord.ButtonStyle.primary, custom_id="add_member")
    async def add_member_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            alliances = await self.get_admin_alliances(interaction.user.id, interaction.guild.id)
            if not alliances:
                await interaction.response.send_message("İttifak üyesi ekleme yetkiniz yok.", ephemeral=True)
                return

            options = [
                discord.SelectOption(
                    label=f"{name}",
                    value=str(alliance_id),
                    description=f"İttifak ID: {alliance_id}"
                ) for alliance_id, name in alliances
            ]

            select = discord.ui.Select(
                placeholder="Bir ittifak seçin",
                options=options,
                custom_id="alliance_select"
            )

            view = discord.ui.View()
            view.add_item(select)

            await interaction.response.send_message(
                "Üye eklemek istediğiniz ittifakı seçin:",
                view=view,
                ephemeral=True
            )

        except Exception as e:
            print(f"Error in add_member_button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred during the process of adding a member.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred during the process of adding a member.",
                    ephemeral=True
                )

    @discord.ui.button(label="Remove Member", emoji="➖", style=discord.ButtonStyle.danger, custom_id="remove_member")
    async def remove_member_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            alliances = await self.get_admin_alliances(interaction.user.id, interaction.guild.id)
            if not alliances:
                await interaction.response.send_message("You are not authorized to delete alliance members.", ephemeral=True)
                return

            options = [
                discord.SelectOption(
                    label=f"{name}",
                    value=str(alliance_id),
                    description=f"Alliance ID: {alliance_id}"
                ) for alliance_id, name in alliances
            ]

            select = discord.ui.Select(
                placeholder="Choose an alliance",
                options=options,
                custom_id="alliance_select_remove"
            )

            view = discord.ui.View()
            view.add_item(select)

            await interaction.response.send_message(
                "Select the alliance you want to delete members from:",
                view=view,
                ephemeral=True
            )

        except Exception as e:
            print(f"Error in remove_member_button: {e}")
            await interaction.response.send_message(
                "An error occurred during the member deletion process.",
                ephemeral=True
            )

    @discord.ui.button(label="View Members", emoji="👥", style=discord.ButtonStyle.primary, custom_id="view_members")
    async def view_members_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            alliances = await self.get_admin_alliances(interaction.user.id, interaction.guild.id)
            if not alliances:
                await interaction.response.send_message("You are not authorized to screen alliance members.", ephemeral=True)
                return

            options = [
                discord.SelectOption(
                    label=f"{name}",
                    value=str(alliance_id),
                    description=f"Alliance ID: {alliance_id}"
                ) for alliance_id, name in alliances
            ]

            select = discord.ui.Select(
                placeholder="Choose an alliance",
                options=options,
                custom_id="alliance_select_view"
            )

            view = discord.ui.View()
            view.add_item(select)

            await interaction.response.send_message(
                "Select the alliance whose members you want to view:",
                view=view,
                ephemeral=True
            )

        except Exception as e:
            print(f"Error in view_members_button: {e}")
            await interaction.response.send_message(
                "An error occurred while viewing the member list.",
                ephemeral=True
            )

    @discord.ui.button(label="Main Menu", emoji="🏠", style=discord.ButtonStyle.secondary, custom_id="main_menu")
    async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.cog.show_main_menu(interaction)
        except Exception as e:
            print(f"Error in main_menu_button: {e}")
            await interaction.response.send_message(
                "An error occurred during return to the main menu.",
                ephemeral=True
            )

class PaginatedDeleteView(discord.ui.View):
    def __init__(self, pages, original_callback):
        super().__init__(timeout=7200)
        self.current_page = 0
        self.pages = pages
        self.original_callback = original_callback
        self.total_pages = len(pages)
        self.update_view()

    def update_view(self):
        self.clear_items()
        
        select = discord.ui.Select(
            placeholder=f"Select alliance to delete ({self.current_page + 1}/{self.total_pages})",
            options=self.pages[self.current_page]
        )
        select.callback = self.original_callback
        self.add_item(select)
        
        previous_button = discord.ui.Button(
            label="◀️",
            style=discord.ButtonStyle.grey,
            custom_id="previous",
            disabled=(self.current_page == 0)
        )
        previous_button.callback = self.previous_callback
        self.add_item(previous_button)

        next_button = discord.ui.Button(
            label="▶️",
            style=discord.ButtonStyle.grey,
            custom_id="next",
            disabled=(self.current_page == len(self.pages) - 1)
        )
        next_button.callback = self.next_callback
        self.add_item(next_button)

    async def previous_callback(self, interaction: discord.Interaction):
        self.current_page = (self.current_page - 1) % len(self.pages)
        self.update_view()
        
        embed = discord.Embed(
            title="🗑️ Delete Alliance",
            description=(
                "**⚠️ Warning: This action cannot be undone!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "1️⃣ Select an alliance from the dropdown menu\n"
                "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                f"**Current Page:** {self.current_page + 1}/{self.total_pages}\n"
                f"**Total Alliances:** {sum(len(page) for page in self.pages)}\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_callback(self, interaction: discord.Interaction):
        self.current_page = (self.current_page + 1) % len(self.pages)
        self.update_view()
        
        embed = discord.Embed(
            title="🗑️ Delete Alliance",
            description=(
                "**⚠️ Warning: This action cannot be undone!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "1️⃣ Select an alliance from the dropdown menu\n"
                "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                f"**Current Page:** {self.current_page + 1}/{self.total_pages}\n"
                f"**Total Alliances:** {sum(len(page) for page in self.pages)}\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.edit_message(embed=embed, view=self)

class PaginatedChannelView(discord.ui.View):
    def __init__(self, channels, original_callback):
        super().__init__(timeout=7200)
        self.current_page = 0
        self.channels = channels
        self.original_callback = original_callback
        self.items_per_page = 25
        self.pages = [channels[i:i + self.items_per_page] for i in range(0, len(channels), self.items_per_page)]
        self.total_pages = len(self.pages)
        self.update_view()

    def update_view(self):
        self.clear_items()
        
        current_channels = self.pages[self.current_page]
        channel_options = [
            discord.SelectOption(
                label=f"#{channel.name}"[:100],
                value=str(channel.id),
                description=f"Channel ID: {channel.id}" if len(f"#{channel.name}") > 40 else None,
                emoji="📢"
            ) for channel in current_channels
        ]
        
        select = discord.ui.Select(
            placeholder=f"Select channel ({self.current_page + 1}/{self.total_pages})",
            options=channel_options
        )
        select.callback = self.original_callback
        self.add_item(select)
        
        if self.total_pages > 1:
            previous_button = discord.ui.Button(
                label="◀️",
                style=discord.ButtonStyle.grey,
                custom_id="previous",
                disabled=(self.current_page == 0)
            )
            previous_button.callback = self.previous_callback
            self.add_item(previous_button)

            next_button = discord.ui.Button(
                label="▶️",
                style=discord.ButtonStyle.grey,
                custom_id="next",
                disabled=(self.current_page == len(self.pages) - 1)
            )
            next_button.callback = self.next_callback
            self.add_item(next_button)

    async def previous_callback(self, interaction: discord.Interaction):
        self.current_page = (self.current_page - 1) % len(self.pages)
        self.update_view()
        
        embed = interaction.message.embeds[0]
        embed.description = (
            f"**Page:** {self.current_page + 1}/{self.total_pages}\n"
            f"**Total Channels:** {len(self.channels)}\n\n"
            "Please select a channel from the menu below."
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_callback(self, interaction: discord.Interaction):
        self.current_page = (self.current_page + 1) % len(self.pages)
        self.update_view()
        
        embed = interaction.message.embeds[0]
        embed.description = (
            f"**Page:** {self.current_page + 1}/{self.total_pages}\n"
            f"**Total Channels:** {len(self.channels)}\n\n"
            "Please select a channel from the menu below."
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

async def setup(bot):
    try:
        # Prefer using a shared connection created in main.py (attached to bot)
        conn = None
        if hasattr(bot, "_connections") and isinstance(bot._connections, dict):
            conn = bot._connections.get("conn_alliance")

        if conn is None:
            # Fallback: ensure the repository `db` folder exists and open local DB
            from pathlib import Path

            repo_root = Path(__file__).resolve().parents[1]
            db_dir = repo_root / "db"
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
            except Exception as mkdir_exc:
                pass

            db_path = db_dir / "alliance.sqlite"
            conn = sqlite3.connect(str(db_path))

        cog = Alliance(bot, conn)
        await bot.add_cog(cog)
        print(f"✓ Alliance cog loaded successfully")
    except Exception as e:
        print(f"✗ Failed to setup Alliance cog: {e}")
        raise
