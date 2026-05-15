
import sys
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to import from db.mongo_adapters
try:
    from db.mongo_adapters import (
        mongo_enabled, GiftCodesAdapter, AutoRedeemSettingsAdapter, 
        AutoRedeemChannelsAdapter, GiftCodeRedemptionAdapter, 
        AutoRedeemMembersAdapter, AutoRedeemedCodesAdapter
    )
    print("SUCCESS: Imported all adapters from db.mongo_adapters")
    print(f"mongo_enabled: {mongo_enabled()}")
    print(f"AutoRedeemMembersAdapter: {AutoRedeemMembersAdapter}")
    if AutoRedeemMembersAdapter:
        print(f"AutoRedeemMembersAdapter methods: {[m for m in dir(AutoRedeemMembersAdapter) if not m.startswith('_')]}")
except ImportError as e:
    print(f"FAILED: Import from db.mongo_adapters failed: {e}")

# Try to import from root mongo_adapters
try:
    import mongo_adapters
    print("\nSUCCESS: Imported from root mongo_adapters")
    print(f"mongo_adapters.mongo_enabled: {mongo_adapters.mongo_enabled()}")
    print(f"mongo_adapters.AutoRedeemMembersAdapter: {getattr(mongo_adapters, 'AutoRedeemMembersAdapter', 'MISSING')}")
except Exception as e:
    print(f"\nFAILED: Import from root mongo_adapters failed: {e}")
