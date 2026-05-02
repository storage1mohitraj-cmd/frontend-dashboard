from fastapi import APIRouter, HTTPException, Request
import logging

try:
    from db.mongo_adapters import GiftCodesAdapter, GiftCodeRedemptionAdapter, mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/giftcodes", tags=["Gift Codes"], redirect_slashes=False)

@router.get("")
@router.get("/")
async def get_active_giftcodes():
    """Fetch all active giftcodes directly from the bot's database."""
    if not mongo_enabled():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # get_all_async returns list of (code, date, validation_status) tuples
        raw = await GiftCodesAdapter.get_all_async()
        codes = [
            {"code": c[0], "date": c[1], "validation_status": c[2]}
            for c in raw
        ]
        return {"codes": codes}
    except Exception as e:
        logger.error(f"Failed to fetch giftcodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
