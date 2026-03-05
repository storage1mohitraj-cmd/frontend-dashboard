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

# Silence noisy mongo logging
logging.getLogger('pymongo').setLevel(logging.WARNING)

from db.mongo_adapters import AutoRedeemMembersAdapter, mongo_enabled

def diagnose():
    enabled = mongo_enabled()
    print(f"DIAG_ENABLED: {enabled}")
    if not enabled: return

    sample_guilds = ["1394263768132960276", "1285973956424597554"]
    for gid in sample_guilds:
        try:
            members = AutoRedeemMembersAdapter.get_members(gid)
            print(f"DIAG_GUILD_{gid}: {len(members)} MEMBERS")
        except Exception as e:
            print(f"DIAG_ERROR_{gid}: {e}")

if __name__ == "__main__":
    diagnose()
