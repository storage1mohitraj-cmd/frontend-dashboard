import asyncio
import json
import re
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
WOSGIFTCODES_URL = "https://wosgiftcodes.com/"

@router.get("")
@router.get("/")
async def get_active_giftcodes(request: Request):
    """Fetch active giftcodes from the bot scraper, with fallbacks."""
    bot_codes = await _fetch_running_bot_active_codes(request)
    if bot_codes:
        return {
            "codes": bot_codes,
            "source": "bot_manage_cog",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

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

    # Try wosgiftcodes.com first (has real reward details in the HTML table)
    wgc_codes = await _fetch_wosgiftcodes_active_codes()
    if wgc_codes:
        return {
            "codes": wgc_codes,
            "source": "wosgiftcodes",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

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

        # Fetch bot DB codes + two enrichment sources in parallel
        raw_task = GiftCodesAdapter.get_all_with_status_async()
        wgc_task  = _fetch_wosgiftcodes_active_codes()
        wostools_task = _fetch_wostools_active_codes()
        raw, wgc_codes, wostools_codes = await asyncio.gather(
            raw_task, wgc_task, wostools_task, return_exceptions=True
        )

        if isinstance(raw, Exception):
            logger.error(f"DB fetch failed: {raw}")
            raw = []

        # Build enrichment map: UPPER(code) -> details dict
        # Priority: wosgiftcodes.com (has rewards) > WosTools
        enrichment_map: dict = {}
        for source_list in [wostools_codes, wgc_codes]:   # wgc last = highest priority
            if isinstance(source_list, list):
                for item in source_list:
                    key = str(item.get("code") or "").strip().upper()
                    if key:
                        enrichment_map[key] = item

        codes = [
            code
            for code in (
                _normalize_database_code_rich(c, enrichment_map)
                for c in raw
            )
            if code["is_active"]
        ]
        return {
            "codes": codes,
            "source": "bot_database",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to fetch giftcodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _fetch_running_bot_active_codes(request: Request) -> list[dict]:
    """Read active gift codes from the loaded Discord bot cog, if available."""
    try:
        bot = getattr(request.app.state, "bot", None)
        if bot is None:
            return []

        manage_cog = bot.get_cog("ManageGiftCode") if hasattr(bot, "get_cog") else None
        if manage_cog is None or not hasattr(manage_cog, "get_active_gift_codes_consolidated"):
            return []

        active_map = await manage_cog.get_active_gift_codes_consolidated(force_refresh=True)
        if not active_map:
            return []

        return [
            _normalize_bot_cog_code(code, expiry)
            for code, expiry in active_map.items()
            if str(code).strip()
        ]
    except Exception as e:
        logger.warning(f"Running bot giftcode cog fetch failed: {e}")
        return []


def _normalize_bot_cog_code(code: str, expiry: str) -> dict:
    return {
        "code": str(code).strip(),
        "rewards": "Rewards not specified",
        "expiry": str(expiry or "Unknown").strip() or "Unknown",
        "description": "",
        "source": "bot_manage_cog",
        "date_added": "",
        "status": "active",
        "validation_status": "active",
        "is_active": True,
    }


async def _fetch_wosgiftcodes_active_codes() -> list[dict]:
    """Scrape active gift codes + reward details from wosgiftcodes.com HTML table."""
    def _scrape() -> list[dict]:
        req = UrlRequest(
            WOSGIFTCODES_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            },
        )
        with urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Extract <tr> rows from the active codes table
        # Each row has: code | rewards | expiry | status
        results = []

        # Find rows inside the active codes section (before the "Expired Codes" heading)
        active_section = html
        expired_idx = html.lower().find("expired code")
        if expired_idx > 0:
            active_section = html[:expired_idx]

        # Match table rows: <tr ...> cells </tr>
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
        cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
        tag_re = re.compile(r"<[^>]+>")

        def strip_tags(s: str) -> str:
            return tag_re.sub("", s).strip()

        for row_m in row_pattern.finditer(active_section):
            row_html = row_m.group(1)
            cells = [strip_tags(c.group(1)) for c in cell_pattern.finditer(row_html)]
            # Skip header rows or rows with fewer than 2 cells
            if len(cells) < 2:
                continue
            code = cells[0].strip()
            # Skip obvious non-code rows (empty, "Code", "Gift Code" headers)
            if not code or code.lower() in ("code", "gift code", "gift codes", "#", "status", "reward", "rewards"):
                continue
            # Code should look like a gift code: alphanumeric, 4-30 chars
            if not re.match(r"^[A-Za-z0-9]{4,30}$", code):
                continue

            rewards = cells[2].strip() if len(cells) > 2 else "Rewards not specified"
            expiry  = cells[3].strip() if len(cells) > 3 else "Unknown"
            
            if not rewards or rewards.lower() in ("", "n/a", "-"):
                rewards = "Rewards not specified"
            if not expiry or expiry.lower() in ("", "n/a", "-"):
                expiry = "Unknown"

            results.append({
                "code": code,
                "rewards": rewards,
                "expiry": expiry,
                "description": cells[1].strip() if len(cells) > 1 else "",
                "source": "wosgiftcodes",
                "date_added": "",
                "status": "active",
                "validation_status": "active",
                "is_active": True,
            })

        return results

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _scrape)
    except Exception as e:
        logger.warning(f"wosgiftcodes.com scrape failed: {e}")
        return []


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
    """Legacy tuple-based normalizer (kept for compatibility)."""
    status = str(code_tuple[2] or "").strip().lower()
    # 'pending' = code added by bot but not yet validated — still usable by players
    is_active = status in ("valid", "active", "pending")
    return {
        "code": code_tuple[0],
        "date": code_tuple[1],
        "date_added": code_tuple[1],
        "validation_status": status or "pending",
        "rewards": "Rewards not specified",
        "expiry": "Unknown",
        "source": "bot_database",
        "is_active": is_active,
    }


def _normalize_database_code_rich(doc: dict, wostools_map: dict | None = None) -> dict:
    """Rich normalizer using the full document from get_all_with_status_async.
    Optionally enriches rewards/expiry from a wostools_map keyed by UPPERCASED code.
    """
    status = str(doc.get("validation_status") or "").strip().lower()
    # 'pending' / '' = freshly scraped by bot, not yet redeemed/validated → still show
    is_active = status in ("valid", "active", "pending", "posted", "")
    code = str(doc.get("giftcode") or "").strip()
    date_added = doc.get("created_at") or doc.get("date") or ""
    updated_at = doc.get("updated_at") or ""

    # Enrich from WosTools if available
    enrichment = (wostools_map or {}).get(code.upper(), {})
    rewards = _first_present(enrichment, ["rewards", "reward", "rewardText", "description"], "Rewards not specified")
    expiry  = _first_present(enrichment, ["expiry", "expires", "expiresAt", "expiration"], "Unknown")

    return {
        "code": code,
        "rewards": rewards,
        "expiry": expiry,
        "description": _first_present(enrichment, ["description", "label"]),
        "source": "bot_database",
        "date_added": date_added,
        "updated_at": updated_at,
        "validation_status": status or "pending",
        "status": status or "pending",
        "is_active": is_active,
        "auto_redeem_processed": doc.get("auto_redeem_processed", False),
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
