from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

try:
    from db.mongo_adapters import (
        AllianceMonitoringAdapter, 
        AllianceMembersAdapter, 
        FurnaceHistoryAdapter, 
        AlliancesAdapter,
        mongo_enabled
    )
except ImportError:
    mongo_enabled = lambda: False
    AllianceMonitoringAdapter = None
    AllianceMembersAdapter = None
    FurnaceHistoryAdapter = None
    AlliancesAdapter = None

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
async def get_monitor_history(guild_id: int, alliance_id: Optional[int] = None, limit: int = 50):
    if not mongo_enabled():
        return []
    
    try:
        if not alliance_id:
            monitors = await AllianceMonitoringAdapter.get_all_monitors_async()
            monitor = next((m for m in monitors if m['guild_id'] == guild_id), None)
            if not monitor:
                return []
            alliance_id = monitor['alliance_id']
        
        # Fetch furnace history
        # Note: We might need a more comprehensive history fetching that includes name changes
        # For now, let's fetch furnace changes and mock others or fetch from member_history if we add tracking there
        
        furnace_history = await FurnaceHistoryAdapter.get_recent_changes_async(days=7, alliance_id=alliance_id)
        
        # Transform for frontend
        history = []
        for h in furnace_history:
            history.append({
                "type": "furnace",
                "fid": h.get("_id"),
                "nickname": h.get("nickname"),
                "growth": h.get("total_growth"),
                "timestamp": datetime.utcnow().isoformat() # Placeholder as aggregation loses exact timestamp
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
                "fid": str(m.get('fid')),
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
