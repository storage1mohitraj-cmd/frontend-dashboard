import discord
from discord.ext import commands
import sqlite3
import asyncio
import os
import sys
from pathlib import Path

# Add repo root to path
repo_root = str(Path(__file__).resolve().parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from cogs.bot_operations import BotOperations

async def test_tree():
    bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
    
    cogs_to_load = [
        "cogs.start_menu",
        "cogs.alliance",
        "cogs.alliance_member_operations",
        "cogs.changes",
        "cogs.web_search",
        "cogs.welcome_channel",
        "cogs.control",
        "cogs.gift_operations",
        "cogs.manage_giftcode",
        "cogs.id_channel",
        "cogs.bot_operations",
        "cogs.remote_access",
        "cogs.fid_commands",
        "cogs.record_commands",
        "cogs.bear_trap",
        "cogs.bear_trap_editor",
        "cogs.attendance",
        "cogs.minister_schedule",
        "cogs.other_features",
        "cogs.support_operations",
        "cogs.minister_menu",
        "cogs.playerinfo",
        "cogs.reminder_system",
        "cogs.birthday_system",
        "cogs.events",
        "cogs.server_age",
        "cogs.personalise_chat",
        "cogs.music",
        "cogs.voice_conversation",
        "cogs.tts",
        "cogs.auto_translate",
        "cogs.message_extractor",
        "cogs.tictactoe",
        "cogs.alliance_monitor",
    ]
    
    for cog_name in cogs_to_load:
        try:
            if cog_name == "cogs.bot_operations":
                await bot.add_cog(BotOperations(bot, sqlite3.connect(':memory:')))
            else:
                await bot.load_extension(cog_name)
            # print(f"Loaded {cog_name}")
        except Exception as e:
            print(f"Failed to load {cog_name}: {e}")
    
    tree_commands = bot.tree.get_commands()
    print(f"Total commands in bot.tree: {len(tree_commands)}")
    for cmd in tree_commands:
        print(f" - {cmd.name}: {cmd.description}")
        if isinstance(cmd, discord.app_commands.Group):
            for sub in cmd.commands:
                print(f"   └ {sub.name}")

if __name__ == "__main__":
    asyncio.run(test_tree())
