from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel
import logging
import os
import uuid

try:
    from db.mongo_adapters import WelcomeChannelAdapter, BirthdaysAdapter, BirthdayChannelAdapter, AutoTranslateAdapter, mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    if not file:
        return {"status": "error", "message": "No file uploaded"}
    
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'png'
    filename = f"{uuid.uuid4()}.{ext}"
    os.makedirs("data/uploads", exist_ok=True)
    filepath = os.path.join("data/uploads", filename)
    
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
        
    return {"url": f"/api/static/{filename}"}

class WelcomeSettings(BaseModel):
    enabled: bool
    channel_id: str
    bg_image_url: str

@router.get("/welcome/{guild_id}")
async def get_welcome_settings(guild_id: int):
    if not mongo_enabled():
        return {"enabled": False, "channel_id": "", "bg_image_url": ""}
    
    doc = await WelcomeChannelAdapter.get_async(guild_id)
    if not doc:
        return {"enabled": False, "channel_id": "", "bg_image_url": ""}
    
    return {
        "enabled": doc.get("enabled", False),
        "channel_id": str(doc.get("channel_id", "")) if doc.get("channel_id") else "",
        "bg_image_url": doc.get("bg_image_url", "")
    }

@router.post("/welcome/{guild_id}")
async def save_welcome_settings(guild_id: int, settings: WelcomeSettings):
    if not mongo_enabled():
        return {"status": "error", "message": "MongoDB not enabled"}
    
    channel_id = int(settings.channel_id) if settings.channel_id else 0
    await WelcomeChannelAdapter.set_async(guild_id, channel_id, settings.enabled)
    if settings.bg_image_url:
        await WelcomeChannelAdapter.set_bg_image_async(guild_id, settings.bg_image_url)
    return {"status": "success"}

class BirthdaySettings(BaseModel):
    channel_id: str

@router.get("/birthday/{guild_id}")
async def get_birthday_settings(guild_id: int):
    if not mongo_enabled() or not BirthdayChannelAdapter:
        return {"channel_id": ""}
    
    channel_id = await BirthdayChannelAdapter.get_async(guild_id)
    return {"channel_id": str(channel_id) if channel_id else ""}

@router.post("/birthday/{guild_id}")
async def save_birthday_settings(guild_id: int, settings: BirthdaySettings):
    if not mongo_enabled() or not BirthdayChannelAdapter:
        return {"status": "error", "message": "MongoDB not enabled"}
    
    channel_id = int(settings.channel_id) if settings.channel_id else 0
    if channel_id:
        await BirthdayChannelAdapter.set_async(guild_id, channel_id)
    return {"status": "success"}

@router.get("/translate/{guild_id}")
async def get_translate_configs(guild_id: int):
    if not mongo_enabled():
        return []
    configs = await AutoTranslateAdapter.get_guild_configs_async(guild_id)
    return configs

class TranslateSettings(BaseModel):
    config_id: str | None = None
    name: str
    source_channel_id: str
    target_channel_id: str
    source_language: str
    target_language: str
    style: str
    enabled: bool

@router.post("/translate/{guild_id}")
async def save_translate_configs(guild_id: int, settings: TranslateSettings):
    if not mongo_enabled():
        return {"status": "error", "message": "MongoDB not enabled"}
    
    data = {
        "name": settings.name,
        "source_channel_id": int(settings.source_channel_id) if settings.source_channel_id else 0,
        "target_channel_id": int(settings.target_channel_id) if settings.target_channel_id else 0,
        "source_language": settings.source_language,
        "target_language": settings.target_language,
        "style": settings.style,
        "enabled": settings.enabled
    }
    
    if settings.config_id:
        success = await AutoTranslateAdapter.update_config_async(settings.config_id, data)
        if not success:
            return {"status": "error", "message": "Failed to update config"}
    else:
        config_id = await AutoTranslateAdapter.create_config_async(guild_id, data)
        if not config_id:
            return {"status": "error", "message": "Failed to create config"}
            
    return {"status": "success"}

@router.delete("/translate/{guild_id}/{config_id}")
async def delete_translate_config(guild_id: int, config_id: str):
    if not mongo_enabled():
        return {"status": "error", "message": "MongoDB not enabled"}
    
    success = await AutoTranslateAdapter.delete_config_async(config_id)
    if success:
        return {"status": "success"}
    return {"status": "error", "message": "Failed to delete config"}
