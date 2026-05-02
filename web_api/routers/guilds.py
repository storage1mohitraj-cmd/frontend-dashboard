from fastapi import APIRouter, HTTPException, Depends, Request
import logging

try:
    from db.mongo_adapters import mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/guilds", tags=["Guilds"])

@router.get("/{guild_id}/stats")
async def get_guild_stats(guild_id: int):
    """Fetch basic stats for a guild."""
    return {
        "member_count": 0,
        "alliance_count": 0,
        "active_users": 0,
        "channels": 0
    }

@router.get("/{guild_id}/channels")
async def get_guild_channels(guild_id: int):
    """Fetch channels for a guild."""
    # In a real app, you would query discord.py bot cache or Discord API
    return [
        {"id": "123", "name": "general", "type": 0},
        {"id": "456", "name": "announcements", "type": 0}
    ]
