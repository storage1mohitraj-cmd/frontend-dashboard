
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from web_api.server import app

print("Registered Routes:")
for route in app.routes:
    if hasattr(route, 'path'):
        print(f"{route.methods} {route.path}")
