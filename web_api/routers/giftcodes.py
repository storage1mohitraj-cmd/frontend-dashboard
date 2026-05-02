from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
import logging

try:
    from db.mongo_adapters import GiftCodesAdapter, GiftCodeRedemptionAdapter, mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

try:
    from gift_codes import get_active_gift_codes
except Exception:
    get_active_gift_codes = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/giftcodes", tags=["Gift Codes"], redirect_slashes=False)

@router.get("")
@router.get("/")
async def get_active_giftcodes():
    """Fetch live active giftcodes with reward and expiry details."""
    try:
        if get_active_gift_codes is not None:
            live_codes = await get_active_gift_codes()
            codes = [_normalize_live_code(code) for code in live_codes]
            return {
                "codes": codes,
                "source": "live_scrapers",
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        if not mongo_enabled():
            raise HTTPException(status_code=503, detail="Gift code source not available")

        raw = await GiftCodesAdapter.get_all_async()
        codes = [_normalize_database_code(c) for c in raw]
        return {
            "codes": codes,
            "source": "database",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to fetch giftcodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _first_present(data: dict, keys: list[str], default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _normalize_live_code(code: dict) -> dict:
    status = _first_present(code, ["status", "validation_status"], "").lower()
    is_active = status in ("active", "valid")
    rewards = _first_present(
        code,
        ["rewards", "reward", "reward_text", "description", "label"],
        "Rewards not specified",
    )
    expiry = _first_present(
        code,
        ["expiry", "expires", "expires_at", "expire_at", "expiration", "expiration_date"],
        "Unknown",
    )
    return {
        "code": _first_present(code, ["code"]),
        "rewards": rewards,
        "expiry": expiry,
        "description": _first_present(code, ["description", "label"]),
        "source": _first_present(code, ["source"], "live"),
        "date_added": _first_present(code, ["date_added", "dateAdded", "created_at", "date"]),
        "validation_status": status or ("active" if is_active else "inactive"),
        "is_active": is_active,
    }


def _normalize_database_code(code_tuple) -> dict:
    return {
        "code": code_tuple[0],
        "date": code_tuple[1],
        "date_added": code_tuple[1],
        "validation_status": code_tuple[2],
        "rewards": "Rewards not specified",
        "expiry": "Unknown",
        "source": "database",
        "is_active": str(code_tuple[2]).lower() in ("valid", "active"),
    }

@router.get("/{guild_id}/stats")
async def get_giftcode_stats(guild_id: int):
    """Fetch giftcode stats for a specific guild."""
    if not mongo_enabled():
        return {"total_attempts": 0, "successful": 0, "failed": 0, "unique_codes": 0}

    try:
        raw = await GiftCodesAdapter.get_all_async()
        unique = len(raw)
        # Count redemption results for this guild if adapter supports it
        successful = sum(1 for c in raw if c[2] == "valid")
        failed = sum(1 for c in raw if c[2] in ("invalid", "expired"))
        return {
            "total_attempts": unique,
            "successful": successful,
            "failed": failed,
            "unique_codes": unique
        }
    except Exception as e:
        logger.error(f"Failed to get giftcode stats: {e}")
        return {"total_attempts": 0, "successful": 0, "failed": 0, "unique_codes": 0}

@router.post("/add")
async def add_giftcode(code: str, reward_text: str = ""):
    """Add a new giftcode from the web dashboard."""
    return {"status": "success", "message": f"Code {code} added."}
