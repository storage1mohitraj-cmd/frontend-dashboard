import os
import sys
from pathlib import Path

# Add the bot directory to sys.path
repo_root = str(Path(__file__).resolve().parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import logging
from dotenv import load_dotenv
load_dotenv()

# Set up logging to stdout
logging.basicConfig(level=logging.INFO)

from db.mongo_adapters import AutoRedeemMembersAdapter, mongo_enabled

def diagnose():
    enabled = mongo_enabled()
    print(f"MongoDB enabled: {enabled}")
    if not enabled:
        print("MONGO_URI not detected in environment")
        return

    # Check some sample guilds from my earlier JSON check
    sample_guilds = ["1394263768132960276", "1285973956424597554"]
    for gid in sample_guilds:
        try:
            members = AutoRedeemMembersAdapter.get_members(gid)
            print(f"Guild {gid}: found {len(members)} members via Adapter")
        except Exception as e:
            print(f"Error for guild {gid}: {e}")

if __name__ == "__main__":
    diagnose()
