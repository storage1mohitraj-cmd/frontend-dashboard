
import discord
from discord.ext import commands
import asyncio
import os
import sys
from pathlib import Path

# Add repo root to path
repo_root = str(Path(__file__).resolve().parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app import bot, TOKEN

async def check_cogs():
    try:
        # We don't want to run the bot fully, just load it and check setup_hook
        # But setup_hook is called by start()
        # So we can't easily check without starting
        pass

if __name__ == "__main__":
    print(f"Bot defined: {bot}")
    print(f"Bot class: {type(bot)}")
    print(f"Cogs to load: {getattr(bot, 'cogs', 'No cogs attribute')}")
