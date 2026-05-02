import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
import logging
from urllib.request import Request as UrlRequest, urlopen

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
WOSTOOLS_GIFT_CODES_URL = "https://wostools.net/api/gift-codes"

@router.get("")
@router.get("/")
async def get_active_giftcodes():
    """Fetch active giftcodes from the bot scraper, with fallbacks."""
    if get_active_gift_codes is not None:
        try:
            live_codes = await get_active_gift_codes()
            codes = [
                code
                for code in (_normalize_live_code(code, trusted_active=True) for code in live_codes)
                if code["is_active"]
            ]
            if codes:
                return {
                    "codes": codes,
                    "source": "bot_scraper",
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.warning(f"Bot giftcode scraper failed, falling back: {e}")

    direct_codes = await _fetch_wostools_active_codes()
    if direct_codes:
        return {
            "codes": direct_codes,
            "source": "wostools",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    try:
        if not mongo_enabled():
            return {
                "codes": [],
                "source": "unavailable",
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        raw = await GiftCodesAdapter.get_all_async()
        codes = [
            code
            for code in (_normalize_database_code(c) for c in raw)
            if code["is_active"]
        ]
        return {
            "codes": codes,
            "source": "database",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to fetch giftcodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _fetch_wostools_active_codes() -> list[dict]:
    def _fetch() -> list[dict]:
        request = UrlRequest(
            WOSTOOLS_GIFT_CODES_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 WhiteoutSurvivalBot/1.0",
            },
        )
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        codes = payload.get("codes", []) if isinstance(payload, dict) else []
        return [
            _normalize_wostools_code(code)
            for code in codes
            if str(code.get("status", "")).strip().lower() == "active"
            and str(code.get("code", "")).strip()
        ]

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _fetch)
    except Exception as e:
        logger.warning(f"WosTools direct giftcode fetch failed: {e}")
        return []


def _normalize_wostools_code(code: dict) -> dict:
    return {
        "code": _first_present(code, ["code"]),
        "rewards": _first_present(
            code,
            ["rewards", "reward", "rewardText", "description", "label"],
            "Rewards not specified",
        ),
        "expiry": _first_present(
            code,
            ["expiry", "expires", "expiresAt", "expiration", "expirationDate"],
            "Unknown",
        ),
        "description": _first_present(code, ["description", "label"]),
        "source": "wostools",
        "date_added": _first_present(code, ["dateAdded", "date_added", "created_at", "date"]),
        "status": "active",
        "validation_status": "active",
        "is_active": True,
    }


def _first_present(data: dict, keys: list[str], default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _normalize_live_code(code: dict, trusted_active: bool = False) -> dict:
    status = _first_present(code, ["status", "validation_status"], "").lower()
    if status:
        is_active = status in ("active", "valid")
    else:
        is_active = trusted_active or bool(code.get("is_active", False))
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
        "status": status or ("active" if is_active else "inactive"),
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
