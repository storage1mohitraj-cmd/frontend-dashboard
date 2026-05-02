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
    """Fetches servers the user is an admin of, with bot presence info."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Fetch user's guilds from Discord API
    async with httpx.AsyncClient() as client:
        r = await client.get(
            'https://discord.com/api/users/@me/guilds',
            headers={"Authorization": auth_header}
        )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        guilds = r.json()

    # Get IDs of guilds the bot is in (from bot cache if available)
    bot_guilds_info = {}
    _bot = getattr(request.app.state, 'bot', None)
    if _bot is not None:
        try:
            bot_guilds_info = {str(g.id): g for g in _bot.guilds}
        except Exception:
            pass

    # Filter for admin guilds (ADMINISTRATOR or MANAGE_GUILD permission)
    admin_guilds = []
    for g in guilds:
        perms = int(g.get("permissions", 0))
        if (perms & 0x8) == 0x8 or (perms & 0x20) == 0x20:
            # Check lock status
            lock_status = "Unlocked"
            if mongo_enabled():
                try:
                    is_locked = await ServerLimitsAdapter.is_server_locked(int(g["id"]))
                    if is_locked:
                        lock_status = "Locked"
                except Exception:
                    pass

            g["bot_lock_status"] = lock_status
            if str(g["id"]) in bot_guilds_info:
                g["bot_present"] = True
                g["approximate_member_count"] = bot_guilds_info[str(g["id"])].member_count
            else:
                g["bot_present"] = False
            admin_guilds.append(g)

    return {"servers": admin_guilds}


