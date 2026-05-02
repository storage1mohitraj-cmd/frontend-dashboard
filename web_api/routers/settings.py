from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import logging

try:
    from db.mongo_adapters import WelcomeChannelAdapter, BirthdaysAdapter, AutoTranslateAdapter, mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["Settings"])

class WelcomeSettings(BaseModel):
    enabled: bool
    channel_id: str
    bg_image_url: str

@router.get("/welcome/{guild_id}")
async def get_welcome_settings(guild_id: int):
    if not mongo_enabled():
        return {"enabled": False, "channel_id": "", "bg_image_url": ""}
    # Placeholder using existing adapter
    return {"enabled": False, "channel_id": "", "bg_image_url": ""}

@router.post("/welcome/{guild_id}")
async def save_welcome_settings(guild_id: int, settings: WelcomeSettings):
    return {"status": "success"}

class BirthdaySettings(BaseModel):
    channel_id: str

@router.get("/birthday/{guild_id}")
async def get_birthday_settings(guild_id: int):
    return {"channel_id": ""}

@router.post("/birthday/{guild_id}")
async def save_birthday_settings(guild_id: int, settings: BirthdaySettings):
    return {"status": "success"}

@router.get("/translate/{guild_id}")
async def get_translate_configs(guild_id: int):
    return []

class TranslateSettings(BaseModel):
    name: str
    source_language: str
    target_language: str
    style: str
    enabled: bool

@router.post("/translate/{guild_id}")
async def save_translate_configs(guild_id: int, settings: TranslateSettings):
    return {"status": "success"}

@router.delete("/translate/{guild_id}/{config_id}")
async def delete_translate_config(guild_id: int, config_id: str):
    return {"status": "success"}
