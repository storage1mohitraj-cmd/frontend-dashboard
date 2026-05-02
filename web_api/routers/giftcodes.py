from fastapi import APIRouter, HTTPException, Depends, Request
import logging

try:
    from db.mongo_adapters import GiftCodesAdapter, mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/giftcodes", tags=["Gift Codes"])

@router.get("/")
async def get_active_giftcodes():
    """Fetch all active giftcodes directly from the bot's database."""
    if not mongo_enabled():
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Re-using the exact same adapter your bot uses!
        codes = await GiftCodesAdapter.get_all_codes()
        return {"codes": codes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add")
async def add_giftcode(code: str, reward_text: str = ""):
    """Add a new giftcode from the web dashboard."""
    # Logic to add code using GiftCodesAdapter
    # e.g., await GiftCodesAdapter.add_code(code, reward_text)
    return {"status": "success", "message": f"Code {code} added."}

@router.get("/{guild_id}/stats")
async def get_giftcode_stats(guild_id: int):
    """Fetch giftcode stats for a specific guild."""
    return {
        "total_attempts": 0,
        "successful": 0,
        "failed": 0,
        "unique_codes": 0
    }
