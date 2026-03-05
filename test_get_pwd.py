import sys
import os
from dotenv import load_dotenv

load_dotenv("f:\\Whiteout Survival Bot\\.env")
sys.path.append("f:\\Whiteout Survival Bot\\DISCORD BOT")

from db.mongo_adapters import ServerAllianceAdapter

pwd = ServerAllianceAdapter.get_password(1147956569271697518)
print(f"Password for 1147956569271697518: {pwd}")

pwd2 = ServerAllianceAdapter.get_password(850787279664185434)
print(f"Password for 850787279664185434: {pwd2}")
