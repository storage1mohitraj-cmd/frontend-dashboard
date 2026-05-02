from fastapi import APIRouter, HTTPException, Request
import httpx
import logging

try:
    from db.mongo_adapters import ServerLimitsAdapter, mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/servers", tags=["Servers"], redirect_slashes=False)

@router.get("")
@router.get("/")
async def get_user_servers(request: Request):
    """Fetches servers the user is an admin of, and checks bot limits."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Fetch user's servers from Discord
    async with httpx.AsyncClient() as client:
        r = await client.get('https://discord.com/api/users/@me/guilds', headers={"Authorization": auth_header})
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        guilds = r.json()
        
    # Filter for servers where user has Manage Server or Admin (permissions & 0x20 or 0x8)
    admin_guilds = []
    for g in guilds:
        perms = int(g.get("permissions", 0))
        if (perms & 0x8) == 0x8 or (perms & 0x20) == 0x20:
            # Check lock status if MongoDB is available
            lock_status = "Unlocked"
            if mongo_enabled():
                try:
                    is_locked = await ServerLimitsAdapter.is_server_locked(int(g["id"]))
                    if is_locked:
                        lock_status = "Locked"
                except Exception:
                    pass
            
            g["bot_lock_status"] = lock_status
            admin_guilds.append(g)

    return {"servers": admin_guilds}
