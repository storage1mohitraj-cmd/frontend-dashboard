from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import httpx
import logging
from datetime import datetime

from cogs.reminder_system import ReminderStorage, TimeParser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reminders", tags=["Reminders"])

class ReminderCreate(BaseModel):
    message: str
    time_str: str
    channel_id: str
    body: str = None
    mention: str = "everyone"
    image_url: str = None
    thumbnail_url: str = None
    footer_text: str = None
    footer_icon_url: str = None
    author_url: str = None

@router.get("/{guild_id}")
async def get_reminders(request: Request, guild_id: int):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized")

    async with httpx.AsyncClient() as client:
        r = await client.get('https://discord.com/api/users/@me', headers={"Authorization": auth_header})
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = r.json()
        user_id = user["id"]

    _bot = getattr(request.app.state, 'bot', None)
    storage = getattr(_bot, 'reminder_system', None).storage if _bot and hasattr(_bot, 'reminder_system') else ReminderStorage()
    
    reminders = storage.get_user_reminders(user_id, limit=50)
    
    guild_channel_ids = set()
    if _bot:
        guild = _bot.get_guild(guild_id)
        if guild:
            guild_channel_ids = {str(c.id) for c in guild.channels}
    
    # Filter by guild_id if available, or check if channel_id belongs to the guild
    server_reminders = []
    for r in reminders:
        # Convert MongoDB ObjectId to string for JSON serialization
        if "_id" in r:
            r["_id"] = str(r["_id"])
            
        r_guild = str(r.get("guild_id")) if r.get("guild_id") else None
        r_channel = str(r.get("channel_id"))
        
        if r_guild == str(guild_id):
            server_reminders.append(r)
        elif r_channel in guild_channel_ids:
            server_reminders.append(r)
            
    return {"reminders": server_reminders}

@router.post("/{guild_id}")
async def create_reminder(request: Request, guild_id: int, payload: ReminderCreate):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized")

    async with httpx.AsyncClient() as client:
        r = await client.get('https://discord.com/api/users/@me', headers={"Authorization": auth_header})
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = r.json()
        user_id = user["id"]

    # Parse time
    reminder_time, recurring_info = TimeParser.parse_time_string(payload.time_str)
    if not reminder_time:
        raise HTTPException(status_code=400, detail="Invalid time format. Please use a format like 'in 5 minutes' or 'tomorrow at 3pm'.")

    _bot = getattr(request.app.state, 'bot', None)
    storage = getattr(_bot, 'reminder_system', None).storage if _bot and hasattr(_bot, 'reminder_system') else ReminderStorage()
    
    reminder_id = storage.add_reminder(
        user_id=str(user_id),
        channel_id=str(payload.channel_id),
        guild_id=str(guild_id),
        message=payload.message,
        body=payload.body,
        reminder_time=reminder_time,
        is_recurring=recurring_info.get("is_recurring", False),
        recurrence_type=recurring_info.get("type"),
        recurrence_interval=recurring_info.get("interval"),
        original_pattern=recurring_info.get("pattern"),
        mention=payload.mention,
        image_url=payload.image_url,
        thumbnail_url=payload.thumbnail_url,
        footer_text=payload.footer_text,
        footer_icon_url=payload.footer_icon_url,
        author_url=payload.author_url
    )
    
    if reminder_id == -1:
        raise HTTPException(status_code=500, detail="Failed to save reminder.")
        
    return {"status": "success", "reminder_id": reminder_id}

@router.delete("/{guild_id}/{reminder_id}")
async def delete_reminder(request: Request, guild_id: int, reminder_id: int):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized")

    async with httpx.AsyncClient() as client:
        r = await client.get('https://discord.com/api/users/@me', headers={"Authorization": auth_header})
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = r.json()
        user_id = user["id"]

    _bot = getattr(request.app.state, 'bot', None)
    storage = getattr(_bot, 'reminder_system', None).storage if _bot and hasattr(_bot, 'reminder_system') else ReminderStorage()
    
    success = storage.delete_reminder(reminder_id, str(user_id))
    
    if success:
        return {"status": "success"}
    else:
        raise HTTPException(status_code=400, detail="Failed to delete reminder. It may not exist or does not belong to you.")
