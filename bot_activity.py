import logging
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from db.mongo_adapters import BotActivityAdapter, mongo_enabled
except Exception:
    BotActivityAdapter = None
    mongo_enabled = lambda: False

logger = logging.getLogger(__name__)


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def publish_bot_activity(
    *,
    workflow: str,
    event_type: str,
    status: str = "info",
    message: str,
    guild_id: Any = None,
    guild_name: Any = None,
    alliance_id: Any = None,
    alliance_name: Any = None,
    fid: Any = None,
    nickname: Any = None,
    state_id: Any = None,
    gift_code: Any = None,
    old_value: Any = None,
    new_value: Any = None,
    reason: Any = None,
    details: Optional[Dict[str, Any]] = None,
) -> bool:
    """Publish a structured live activity event without risking bot workflows."""
    if not mongo_enabled() or BotActivityAdapter is None:
        return False

    try:
        activity = {
            "workflow": _clean(workflow) or "system",
            "event_type": _clean(event_type) or "activity",
            "status": _clean(status) or "info",
            "message": str(message or "Bot activity update")[:500],
            "guild_id": _clean(guild_id),
            "guild_name": _clean(guild_name),
            "alliance_id": _clean(alliance_id),
            "alliance_name": _clean(alliance_name),
            "fid": _clean(fid),
            "nickname": _clean(nickname),
            "state_id": _clean(state_id),
            "gift_code": _clean(gift_code),
            "old_value": old_value,
            "new_value": new_value,
            "reason": _clean(reason),
            "details": details or {},
            "created_at": datetime.utcnow(),
        }
        return await BotActivityAdapter.insert_activity_async(activity)
    except Exception as exc:
        logger.warning("Failed to publish bot activity: %s", exc)
        return False
