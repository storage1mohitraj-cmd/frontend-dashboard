import os
import logging
from datetime import datetime
from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Safety import for mongo
try:
    from db.mongo_adapters import mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Whiteout Survival Bot API",
    description="The modular API powering the web dashboard.",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://whiteout-survival-bot.vercel.app",
        "https://whiteout-survival.vercel.app",
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "timestamp": datetime.utcnow().isoformat(),
        "bot_loaded": hasattr(app.state, "bot") and app.state.bot is not None
    }

# Safe router imports
try:
    from web_api.routers.auth import router as auth_router
    app.include_router(auth_router)
    logger.info("✅ Auth router loaded")
except Exception as e:
    logger.error(f"❌ Failed to load auth router: {e}")

try:
    from web_api.routers.giftcodes import router as giftcodes_router
    app.include_router(giftcodes_router, prefix="/api/giftcodes")
    logger.info("✅ Giftcodes router loaded")
except Exception as e:
    logger.error(f"❌ Failed to load giftcodes router: {e}")

try:
    from web_api.routers.servers import router as servers_router
    app.include_router(servers_router)
    logger.info("✅ Servers router loaded")
except Exception as e:
    logger.error(f"❌ Failed to load servers router: {e}")

try:
    from web_api.routers.guilds import router as guilds_router
    app.include_router(guilds_router)
    logger.info("✅ Guilds router loaded")
except Exception as e:
    logger.error(f"❌ Failed to load guilds router: {e}")

try:
    from web_api.routers.settings import router as settings_router
    app.include_router(settings_router)
    logger.info("✅ Settings router loaded")
except Exception as e:
    logger.error(f"❌ Failed to load settings router: {e}")

try:
    from web_api.routers.reminders import router as reminders_router
    app.include_router(reminders_router)
    logger.info("✅ Reminders router loaded")
except Exception as e:
    logger.error(f"❌ Failed to load reminders router: {e}")

os.makedirs("data/uploads", exist_ok=True)
app.mount("/api/static", StaticFiles(directory="data/uploads"), name="static")

async def start_web_server(bot=None, port: int = 8080):
    app.state.bot = bot
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        loop="asyncio",
        log_level="info"
    )
    server = uvicorn.Server(config)
    logger.info(f"🚀 FastAPI Web Server starting on port {port}")
    await server.serve()
