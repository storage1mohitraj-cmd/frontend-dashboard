from fastapi import APIRouter, HTTPException, Depends, Request
import logging

try:
    from db.mongo_adapters import mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/guilds", tags=["Guilds"])

@router.get("/{guild_id}/stats")
async def get_guild_stats(guild_id: int, request: Request):
    """Fetch basic stats for a guild."""
    _bot = getattr(request.app.state, 'bot', None)
    stats = {
        "member_count": 0,
        "alliance_count": 0,
        "active_users": 0,
        "channels": 0
    }
    
    if _bot:
        guild = _bot.get_guild(guild_id)
        if guild:
            stats["member_count"] = guild.member_count
            stats["channels"] = len(guild.text_channels)
            
    # You could add alliance count here if you query the DB
    return stats

@router.get("/{guild_id}/channels")
async def get_guild_channels(guild_id: int, request: Request):
    """Fetch channels for a guild."""
    _bot = getattr(request.app.state, 'bot', None)
    if not _bot:
        return []
        
    guild = _bot.get_guild(guild_id)
    if not guild:
        return []
        
    channels = []
    for channel in guild.text_channels:
        channels.append({
            "id": str(channel.id),
            "name": channel.name,
            "type": 0
        })
    return channels
