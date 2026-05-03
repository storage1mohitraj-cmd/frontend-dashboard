import discord
from discord.ext import commands

from db.mongo_adapters import RecordsAdapter
from db_utils import get_db_connection
from cogs.login_handler import LoginHandler


def is_global_admin(user_id: int) -> bool:
    """Check if user is a global administrator"""
    try:
        with get_db_connection('settings.sqlite') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM admin WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result is not None
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return False


class RecordCommands(commands.Cog):
    """
    Records management cog.
    
    All record operations are now accessible via the Settings menu:
    /settings -> Records button
    
    This cog is kept for potential future slash command additions.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.login_handler = LoginHandler()
        
        # Furnace level mapping
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

    # All /record commands have been removed.
    # Record operations are now accessible via: /settings -> Records button



async def setup(bot):
    await bot.add_cog(RecordCommands(bot))
