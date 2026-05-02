from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import uvicorn
import logging

try:
    from db.mongo_adapters import mongo_enabled
except ImportError:
    mongo_enabled = lambda: False

import os
from fastapi.staticfiles import StaticFiles

# Import our modular routers
from web_api.routers.auth import router as auth_router
from web_api.routers.giftcodes import router as giftcodes_router
from web_api.routers.servers import router as servers_router
from web_api.routers.guilds import router as guilds_router
from web_api.routers.settings import router as settings_router
from web_api.routers.reminders import router as reminders_router

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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"❌ Validation error for {request.method} {request.url}: {exc.errors()}")
    logger.error(f"📝 Payload that failed: {exc.body}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)},
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

@app.get("/api/test-direct")
async def test_direct():
    return {"message": "Direct API test works"}

# Register all modular routers
app.include_router(status_router)
app.include_router(auth_router)
app.include_router(giftcodes_router, prefix="/api/giftcodes")
app.include_router(servers_router)
app.include_router(guilds_router)
app.include_router(settings_router)
app.include_router(reminders_router)

os.makedirs("data/uploads", exist_ok=True)
app.mount("/api/static", StaticFiles(directory="data/uploads"), name="static")

async def start_web_server(bot=None, port: int = 8080):
    """Starts the FastAPI server on the existing asyncio loop."""
    app.state.bot = bot
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        loop="asyncio",
        log_config=None,  # Prevents uvicorn from using colorama which crashes under PM2
        log_level="info"
    )
    server = uvicorn.Server(config)
    logger.info(f"🚀 FastAPI Web Server running on port {port}")
    
    # Log all registered routes
    logger.info("📋 Registered Routes:")
    for route in app.routes:
        if hasattr(route, 'path'):
            logger.info(f"  {route.methods} {route.path}")
            
    await server.serve()
