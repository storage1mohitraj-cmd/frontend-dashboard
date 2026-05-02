from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

try:
    from db.mongo_adapters import mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

# Import our modular routers
from web_api.routers.auth import router as auth_router
from web_api.routers.giftcodes import router as giftcodes_router
from web_api.routers.servers import router as servers_router
from web_api.routers.guilds import router as guilds_router
from web_api.routers.settings import router as settings_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Whiteout Survival Bot API",
    description="The modular API powering the web dashboard. Runs alongside the Discord bot.",
    version="1.0.0"
)

# CORS ensures the Vercel frontend can call this backend securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://whiteout-survival.vercel.app", 
        "https://whiteout-survival-bot.vercel.app", 
        "http://localhost:3000", 
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

status_router = APIRouter(prefix="/api/status", tags=["Status"])

@status_router.get("/")
async def get_status():
    """Health check for the Oracle VM and Vercel."""
    return {
        "status": "healthy",
        "mongo_connected": mongo_enabled(),
        "bot_online": True
    }

# Register all modular routers
app.include_router(status_router)
app.include_router(auth_router)
app.include_router(giftcodes_router)
app.include_router(servers_router)
app.include_router(guilds_router)
app.include_router(settings_router)

async def start_web_server(port: int = 8080):
    """Starts the FastAPI server on the existing asyncio loop."""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        loop="asyncio",
        log_level="info"
    )
    server = uvicorn.Server(config)
    logger.info(f"🚀 FastAPI Web Server running on port {port}")
    await server.serve()
