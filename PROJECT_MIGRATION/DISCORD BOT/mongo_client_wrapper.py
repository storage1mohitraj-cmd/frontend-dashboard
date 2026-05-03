from db.mongo_client_wrapper import get_mongo_client

# Backwards-compatible shim: re-export the implementation from db/
__all__ = ['get_mongo_client']
