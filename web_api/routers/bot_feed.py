import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request

from admin_utils import format_furnace_level

try:
    from db.mongo_adapters import (
        AllianceEventsAdapter,
        AllianceMonitoringAdapter,
        AutoRedeemSettingsAdapter,
        GiftCodesAdapter,
        GiftCodeRedemptionAdapter,
        mongo_enabled,
    )
except ImportError:
    mongo_enabled = lambda: False
    AllianceEventsAdapter = AllianceMonitoringAdapter = AutoRedeemSettingsAdapter = GiftCodesAdapter = GiftCodeRedemptionAdapter = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bot-feed", tags=["Bot Feed"])

_CACHE: Dict[str, Any] = {"expires_at": 0.0, "payload": None}
_CACHE_TTL_SECONDS = 30


@router.get("")
@router.get("/")
async def get_bot_feed(request: Request, limit: int = 40):
    """Public, cached overview of bot activity for the marketing frontend."""
    now = time.monotonic()
    if _CACHE["payload"] is not None and now < _CACHE["expires_at"]:
        return _CACHE["payload"]

    safe_limit = max(10, min(int(limit or 40), 100))
    bot = getattr(request.app.state, "bot", None)
    guilds = list(getattr(bot, "guilds", []) or [])
    server_lookup = _guild_name_lookup(guilds)
    events = await _build_events(safe_limit, server_lookup)
    gift_codes = await _get_gift_codes()
    monitors = await _get_monitors()
    auto_redeem_enabled = await _get_auto_redeem_enabled()

    payload = {
        "status": "online" if bot and getattr(bot, "is_ready", lambda: False)() else "warming",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cache_ttl_seconds": _CACHE_TTL_SECONDS,
        "summary": {
            "servers": len(guilds),
            "members": sum((getattr(guild, "member_count", 0) or 0) for guild in guilds),
            "active_monitors": len(monitors),
            "auto_redeem_servers": auto_redeem_enabled,
            "active_gift_codes": len(gift_codes),
            "latency_ms": round(bot.latency * 1000) if bot else None,
        },
        "servers": _serialize_guilds(guilds),
        "events": events or _demo_events(),
        "gift_codes": gift_codes,
        "source": "live_cache" if events or guilds or gift_codes else "demo_loop",
    }
    _CACHE["payload"] = payload
    _CACHE["expires_at"] = now + _CACHE_TTL_SECONDS
    return payload


async def _build_events(limit: int, server_lookup: Dict[str, str]) -> List[Dict[str, Any]]:
    if not mongo_enabled():
        return []
    events = []
    if AllianceEventsAdapter is not None:
        raw_events = await AllianceEventsAdapter.get_global_recent_events_async(limit=limit)
        events.extend(_normalize_event(event) for event in raw_events)
    events.extend(await _get_redemption_events(limit, server_lookup))
    events.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    return events[:limit]


async def _get_redemption_events(limit: int, server_lookup: Dict[str, str]) -> List[Dict[str, Any]]:
    if GiftCodeRedemptionAdapter is None:
        return []
    try:
        docs = await GiftCodeRedemptionAdapter.get_recent_redemptions_async(limit=limit)
    except Exception as exc:
        logger.warning("Unable to load redemption feed: %s", exc)
        return []

    events = []
    for doc in docs:
        redemptions = list(doc.get("redemptions") or [])
        latest = redemptions[-1] if redemptions else {}
        guild_id = str(doc.get("guild_id") or "")
        code = str(doc.get("code") or "").strip()
        fid = str(latest.get("fid") or "").strip()
        status = str(latest.get("status") or "processed").replace("_", " ")
        server_name = server_lookup.get(guild_id, "a connected server")
        events.append(
            {
                "id": f"redeem-{doc.get('id')}",
                "type": "redeem",
                "title": "Gift code redeem",
                "message": f"Redeemed code {code} for ID {fid} at {server_name} ({status})",
                "player": "Tracked player",
                "fid": fid,
                "server": server_name,
                "new_value": code,
                "timestamp": _iso(latest.get("redeemed_at") or doc.get("last_redeemed_at") or doc.get("updated_at")),
            }
        )
    return events


async def _get_gift_codes() -> List[Dict[str, Any]]:
    if not mongo_enabled() or GiftCodesAdapter is None:
        return []
    try:
        raw_codes = await GiftCodesAdapter.get_all_with_status_async()
    except Exception as exc:
        logger.warning("Unable to load gift codes for bot feed: %s", exc)
        return []

    active_statuses = {"active", "valid", "pending", "posted", ""}
    codes = []
    for item in raw_codes[:40]:
        status = str(item.get("validation_status") or "").strip().lower()
        if status not in active_statuses:
            continue
        codes.append(
            {
                "code": str(item.get("giftcode") or "").strip(),
                "status": status or "pending",
                "auto_redeem_processed": bool(item.get("auto_redeem_processed", False)),
                "updated_at": _iso(item.get("updated_at") or item.get("created_at") or item.get("date")),
            }
        )
    return [code for code in codes if code["code"]][:12]


async def _get_monitors() -> List[Dict[str, Any]]:
    if not mongo_enabled() or AllianceMonitoringAdapter is None:
        return []
    try:
        return await AllianceMonitoringAdapter.get_all_monitors_async()
    except Exception as exc:
        logger.warning("Unable to load monitor count for bot feed: %s", exc)
        return []


async def _get_auto_redeem_enabled() -> int:
    if not mongo_enabled() or AutoRedeemSettingsAdapter is None:
        return 0
    try:
        settings = await AutoRedeemSettingsAdapter.get_all_enabled_async()
        return len(settings or [])
    except AttributeError:
        try:
            settings = await AutoRedeemSettingsAdapter.get_all_settings_async()
            return sum(1 for item in settings if item.get("enabled"))
        except Exception:
            return 0
    except Exception:
        return 0


def _serialize_guilds(guilds: list) -> List[Dict[str, Any]]:
    serialized = []
    for guild in sorted(guilds, key=lambda g: (getattr(g, "name", "") or "").lower()):
        serialized.append(
            {
                "id": str(getattr(guild, "id", "")),
                "name": getattr(guild, "name", "Unknown server"),
                "members": getattr(guild, "member_count", 0) or 0,
                "icon_url": str(guild.icon.url) if getattr(guild, "icon", None) else None,
            }
        )
    return serialized[:1000]


def _guild_name_lookup(guilds: list) -> Dict[str, str]:
    return {str(getattr(guild, "id", "")): getattr(guild, "name", "connected server") for guild in guilds}


def _normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    event_type = str(event.get("type") or "event").replace("_change", "")
    old_value = event.get("old_value")
    new_value = event.get("new_value")
    title = "Profile updated"
    message = "updated their profile"

    if event_type == "furnace":
        old_level = _format_furnace(old_value)
        new_level = _format_furnace(new_value)
        title = "Furnace upgrade detected"
        if old_level and new_level:
            message = f"upgraded FC from {old_level} to {new_level}"
        elif new_level:
            message = f"reached {new_level}"
    elif event_type == "name":
        title = "Name change detected"
        message = f"changed name from {old_value or 'Unknown'} to {new_value or 'Unknown'}"
    elif event_type == "avatar":
        title = "Avatar change detected"
        message = "changed avatar"
    elif event_type == "state":
        title = "State transfer detected"
        message = f"moved from State {old_value or '?'} to State {new_value or '?'}"

    return {
        "id": str(event.get("id") or f"{event_type}-{event.get('fid', '')}-{event.get('timestamp', '')}"),
        "type": event_type,
        "title": title,
        "message": message,
        "player": event.get("nickname") or "Unknown player",
        "fid": str(event.get("fid") or ""),
        "alliance_id": event.get("alliance_id"),
        "timestamp": _iso(event.get("timestamp")),
        "old_value": old_value,
        "new_value": new_value,
        "old_avatar": old_value if event_type == "avatar" else None,
        "new_avatar": new_value if event_type == "avatar" else event.get("avatar_image"),
    }


def _format_furnace(value: Optional[Any]) -> Optional[str]:
    if value is None or value == "":
        return None
    try:
        return format_furnace_level(int(value))
    except Exception:
        return str(value)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _demo_events() -> List[Dict[str, Any]]:
    avatar_old = "https://cdn.discordapp.com/embed/avatars/1.png"
    avatar_new = "https://cdn.discordapp.com/embed/avatars/4.png"
    return [
        {
            "id": "demo-redeem-lovemom",
            "type": "redeem",
            "title": "Gift code redeem",
            "message": "Redeeming code LoveMoM2026 for Magnus at ICe angel server",
            "player": "Magnus",
            "fid": "720263644",
            "server": "ICe angel",
            "state": "3063",
            "new_value": "LoveMoM2026",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": "demo-furnace-magnus",
            "type": "furnace",
            "title": "Furnace upgrade detected",
            "message": "Magnus State 3063 upgraded FC from FC4-1 to FC4-2",
            "player": "Magnus",
            "fid": "720263644",
            "state": "3063",
            "old_value": "FC4-1",
            "new_value": "FC4-2",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": "demo-avatar-primrose",
            "type": "avatar",
            "title": "Avatar change detected",
            "message": "Primrose changed her avatar",
            "player": "Primrose",
            "old_avatar": avatar_old,
            "new_avatar": avatar_new,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": "demo-name-change",
            "type": "name",
            "title": "Name change detected",
            "message": "A monitored player changed name",
            "player": "ICe angel member",
            "old_value": "Old name",
            "new_value": "New name",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    ]
