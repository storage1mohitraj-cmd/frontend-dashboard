
import discord
from discord.ext import commands
from discord import app_commands
import os
import sys

# Lazy import helpers to prevent load-time crashes
def safe_mongo_enabled():
    try:
        from db.mongo_adapters import mongo_enabled
        return mongo_enabled()
    except Exception as e:
        return f"Error importing mongo_enabled: {e}"

def safe_get_db():
    try:
        from db.mongo_adapters import _get_db
        return _get_db()
    except Exception as e:
        raise ImportError(f"Error importing _get_db: {e}")

class DebugMongoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("DEBUG: DebugMongoCog initialized!")

    async def _debug_logic(self):
        lines = []
        lines.append(f"**Diagnostic Output**")
        try:
            lines.append(f"Python: {sys.version.split()[0]}")
            
            # Check Env Vars
            uri = os.getenv('MONGO_URI')
            db_name = os.getenv('MONGO_DB_NAME')
            lines.append(f"MONGO_URI present: {bool(uri)}")
            lines.append(f"MONGO_DB_NAME: `{db_name}`")
            
            # Check modules
            try:
                import pymongo
                lines.append(f"pymongo: {pymongo.__version__}")
            except ImportError:
                lines.append("pymongo: ❌ MISSING")
                
            try:
                import motor
                lines.append(f"motor: {motor.version if hasattr(motor, 'version') else 'installed'}")
            except ImportError:
                lines.append("motor: ❌ MISSING")

            # Check Adapter Status
            is_enabled = safe_mongo_enabled()
            lines.append(f"mongo_enabled(): `{is_enabled}`")
            
            if isinstance(is_enabled, bool) and is_enabled:
                try:
                    db = safe_get_db()
                    lines.append(f"**Connected Database**")
                    lines.append(f"DB Name: `{db.name}`")
                    
                    # Count documents
                    cols = {
                        'reminders': 'reminders', 
                        'alliance_members': 'alliance_members',
                        'gift_codes': 'gift_codes',
                        'auto_redeem_settings': 'auto_redeem_settings',
                        'users': 'users' # Check users collection too
                    }
                    
                    for name, col_name in cols.items():
                        try:
                            count = db[col_name].count_documents({})
                            lines.append(f"{name}: `{count}` docs")
                        except Exception as e:
                            lines.append(f"{name}: Error {e}")
                            
                except Exception as e:
                    lines.append(f"**Connection Error**: {e}")
            elif isinstance(is_enabled, bool):
                 lines.append("MongoDB is disabled in adapters (MONGO_URI not set?)")
                
        except Exception as e:
            lines.append(f"Fatal Debug Error: {e}")
            import traceback
            lines.append(f"```{traceback.format_exc()[:1000]}```")
            
        return "\n".join(lines)

    @app_commands.command(name="debug_db", description="Debug MongoDB connection and settings")
    async def debug_db_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        output = await self._debug_logic()
        await interaction.followup.send(output)

    @commands.command(name="debug_db")
    async def debug_db_prefix(self, ctx):
        await ctx.send("🔍 Running diagnostics...")
        output = await self._debug_logic()
        await ctx.send(output)

async def setup(bot):
    print("DEBUG: Loading DebugMongoCog (Lazy Mode)...")
    await bot.add_cog(DebugMongoCog(bot))
