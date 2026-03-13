
import os
import logging
from typing import Optional
from pymongo import MongoClient
import motor.motor_asyncio
import asyncio

logger = logging.getLogger(__name__)

# Global client instances for reuse
_async_clients = {}
_sync_clients = {}

def get_mongo_uri() -> str:
    """Get MongoDB URI from environment variables."""
    return os.environ.get('MONGO_URI', 'mongodb://localhost:27017')

async def get_mongo_client(uri: Optional[str] = None, **kwargs) -> motor.motor_asyncio.AsyncIOMotorClient:
    """Get or create an asynchronous MongoDB client."""
    global _async_clients
    if uri is None:
        uri = get_mongo_uri()
    
    if uri not in _async_clients:
        # Add default timeout if not provided
        if 'serverSelectionTimeoutMS' not in kwargs:
            kwargs['serverSelectionTimeoutMS'] = 5000
        _async_clients[uri] = motor.motor_asyncio.AsyncIOMotorClient(uri, **kwargs)
        logger.info(f"✅ Created asynchronous MongoDB client for {uri[:20]}...")
    return _async_clients[uri]

def get_mongo_client_sync(uri: Optional[str] = None, **kwargs) -> MongoClient:
    """Get or create a synchronous MongoDB client."""
    global _sync_clients
    if uri is None:
        uri = get_mongo_uri()
    
    if uri not in _sync_clients:
        # Add default timeout if not provided
        if 'serverSelectionTimeoutMS' not in kwargs:
            kwargs['serverSelectionTimeoutMS'] = 5000
        _sync_clients[uri] = MongoClient(uri, **kwargs)
        logger.info(f"✅ Created synchronous MongoDB client for {uri[:20]}...")
    return _sync_clients[uri]

def mongo_enabled() -> bool:
    """Check if MongoDB is configured and available."""
    return bool(os.environ.get('MONGO_URI'))
