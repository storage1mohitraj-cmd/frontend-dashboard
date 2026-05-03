from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from admin_utils import format_furnace_level

try:
    from db.mongo_adapters import (
        AllianceMonitoringAdapter, 
        AllianceMembersAdapter, 
        FurnaceHistoryAdapter, 
        AlliancesAdapter,
        AllianceEventsAdapter,
        mongo_enabled
    )
except ImportError:
    mongo_enabled = lambda: False
    AllianceMonitoringAdapter = None
    AllianceMembersAdapter = None
    FurnaceHistoryAdapter = None
    AlliancesAdapter = None
    AllianceEventsAdapter = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alliance-monitor", tags=["Alliance Monitor"])

class MonitorSettings(BaseModel):
    guild_id: int
    alliance_id: int
    channel_id: int
    enabled: bool = True
    check_interval: int = 240

@router.get("/alliances")
async def get_all_alliances():
    if not mongo_enabled():
        return []
    
    try:
        alliances = await AlliancesAdapter.get_all()
        return [{"id": a['alliance_id'], "name": a['alliance_name']} for a in alliances]
    except Exception as e:
        logger.error(f"Error getting alliances: {e}")
        return []

@router.get("/status/{guild_id}")
async def get_monitor_status(guild_id: int):
    if not mongo_enabled():
        return {"enabled": False, "message": "MongoDB not enabled"}
    
    try:
        monitors = await AllianceMonitoringAdapter.get_all_monitors_async()
        # Find monitor for this guild
        monitor = next((m for m in monitors if m['guild_id'] == guild_id), None)
        
        if not monitor:
            return {
                "enabled": False,
                "guild_id": guild_id,
                "alliance_id": 0,
                "channel_id": 0,
                "check_interval": 240
            }
        
        return {
            "enabled": bool(monitor['enabled']),
            "guild_id": monitor['guild_id'],
            "alliance_id": monitor['alliance_id'],
            "channel_id": str(monitor['channel_id']),
            "check_interval": monitor['check_interval']
        }
    except Exception as e:
        logger.error(f"Error getting monitor status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings")
async def save_monitor_settings(settings: MonitorSettings):
    if not mongo_enabled():
        return {"status": "error", "message": "MongoDB not enabled"}
    
    try:
        success = await AllianceMonitoringAdapter.upsert_monitor_async(
            guild_id=settings.guild_id,
            alliance_id=settings.alliance_id,
            channel_id=settings.channel_id,
            enabled=1 if settings.enabled else 0,
            check_interval=settings.check_interval
        )
        
        if success:
            return {"status": "success", "message": "Settings saved"}
        else:
            return {"status": "error", "message": "Failed to save settings"}
    except Exception as e:
        logger.error(f"Error saving monitor settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{guild_id}")
async def get_monitor_history(guild_id: int, limit: int = 50):
    if not mongo_enabled():
        return []
    
    try:
        events = await AllianceEventsAdapter.get_recent_events_async(guild_id, limit=limit)
        
        # Format for frontend
        history = []
        for e in events:
            # Standardize type names for frontend CSS
            e_type = e.get('type', 'event').replace('_change', '')
            
            val_text = ""
            if e_type == 'furnace':
                val_text = f"reached {format_furnace_level(e.get('new_value'))}"
            elif e_type == 'name':
                val_text = f"changed name to {e.get('new_value')}"
            elif e_type == 'avatar':
                val_text = "updated their avatar"
            elif e_type == 'state':
                val_text = f"moved to State #{e.get('new_value')}"
            else:
                val_text = "updated their profile"

            history.append({
                "type": e_type,
                "id": e.get("fid"),
                "nickname": e.get("nickname"),
                "value_text": val_text,
                "timestamp": e.get("timestamp")
            })
            
        return history
    except Exception as e:
        logger.error(f"Error getting monitor history: {e}")
        return []

@router.get("/members/{guild_id}")
async def get_monitored_members(guild_id: int, alliance_id: Optional[int] = None):
    if not mongo_enabled():
        return []
    
    try:
        if not alliance_id:
            monitors = await AllianceMonitoringAdapter.get_all_monitors_async()
            monitor = next((m for m in monitors if m['guild_id'] == guild_id), None)
            if not monitor:
                return []
            alliance_id = monitor['alliance_id']
            
        all_members = await AllianceMembersAdapter.get_all_members_async()
        
        # Filter by alliance
        alliance_members = [
            m for m in all_members 
            if int(m.get('alliance') or m.get('alliance_id') or 0) == int(alliance_id)
        ]
        
        # Clean up and format
        result = []
        for m in alliance_members:
            result.append({
                "id": str(m.get('fid')),
                "nickname": m.get('nickname'),
                "furnace_lv": m.get('furnace_lv', 0),
                "avatar_image": m.get('avatar_image', ''),
                "state_id": m.get('state_id', ''),
                "last_checked": m.get('last_checked').isoformat() if isinstance(m.get('last_checked'), datetime) else m.get('last_checked')
            })
            
        return result
    except Exception as e:
        logger.error(f"Error getting monitored members: {e}")
        return []
