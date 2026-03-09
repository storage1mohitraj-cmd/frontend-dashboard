import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Ensure the project root (the directory that contains the `db` package)
# is on sys.path so imports like `db.mongo_adapters` work regardless of
# the current working directory (some hosts run with a different cwd).
proj_root = os.path.dirname(__file__)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

# Try to import the real mongo adapters from the packaged `db` package.
# If that fails (running from a different working dir), attempt to load
# the migration copy of the adapters (used on the VM) before falling
# back to the lightweight shim.
try:
    from db.mongo_adapters import *  # type: ignore
    __all__ = [
        'mongo_enabled', 'UserTimezonesAdapter', 'BirthdaysAdapter', 'BirthdayChannelAdapter', 
        'UserProfilesAdapter', 'GiftcodeStateAdapter', 'GiftCodesAdapter', 'AllianceMembersAdapter', 
        'AutoRedeemSettingsAdapter', 'AutoRedeemChannelsAdapter', 'WelcomeChannelAdapter',
        'AutoRedeemMembersAdapter', 'GiftCodeRedemptionAdapter', 'AutoRedeemedCodesAdapter', '_get_db'
    ]
except Exception as primary_exc:
    # fallback: try loading the migrated adapter file directly by path
    try:
        import importlib.machinery, importlib.util
        migration_path = os.path.join(proj_root, 'PROJECT_MIGRATION', 'DISCORD BOT', 'db', 'mongo_adapters.py')
        if os.path.isfile(migration_path):
            loader = importlib.machinery.SourceFileLoader('migration_db.mongo_adapters', migration_path)
            spec = importlib.util.spec_from_loader(loader.name, loader)
            mod = importlib.util.module_from_spec(spec)
            loader.exec_module(mod)
            # copy symbols
            for name in getattr(mod, '__all__', [k for k in dir(mod) if not k.startswith('_')]):
                globals()[name] = getattr(mod, name)
            __all__ = getattr(mod, '__all__', None) or __all__
        else:
            raise FileNotFoundError(migration_path)
    except Exception as secondary_exc:
        logging.getLogger(__name__).warning(
            'db.mongo_adapters import failed (%s); migration copy failed (%s); using local fallback shim',
            primary_exc, secondary_exc
        )

    def mongo_enabled() -> bool:
        return False

    class _FallbackAdapter:
        @staticmethod
        def load_all():
            return {}

        @staticmethod
        def get(*args, **kwargs):
            return None

        @staticmethod
        def set(*args, **kwargs):
            return False

        @staticmethod
        def remove(*args, **kwargs):
            return False

        @staticmethod
        def clear_all(*args, **kwargs):
            return False

    # Provide minimal fallback classes expected by the codebase
    class UserTimezonesAdapter(_FallbackAdapter):
        pass

    class BirthdaysAdapter(_FallbackAdapter):
        pass

    class BirthdayChannelAdapter(_FallbackAdapter):
        pass

    class UserProfilesAdapter(_FallbackAdapter):
        @staticmethod
        def load_all() -> Dict[str, Any]:
            return {}

        @staticmethod
        def get(user_id: str) -> Optional[Dict[str, Any]]:
            return None

        @staticmethod
        def set(user_id: str, data: Dict[str, Any]) -> bool:
            return False

    class GiftcodeStateAdapter(_FallbackAdapter):
        @staticmethod
        def get_state() -> Dict[str, Any]:
            return {}

        @staticmethod
        def set_state(state: Dict[str, Any]) -> bool:
            return False

    class GiftCodesAdapter(_FallbackAdapter):
        @staticmethod
        def get_all():
            return []

        @staticmethod
        def insert(code: str, date: str, validation_status: str = 'pending') -> bool:
            return False

        @staticmethod
        def update_status(code: str, validation_status: str) -> bool:
            return False

        @staticmethod
        def delete(code: str) -> bool:
            return False

    class AllianceMembersAdapter(_FallbackAdapter):
        @staticmethod
        def load_all():
            return {}

    class AutoRedeemSettingsAdapter(_FallbackAdapter):
        @staticmethod
        def get_settings(guild_id: int):
            return None
        
        @staticmethod
        def get_all_settings():
            return []
        
        @staticmethod
        def set_enabled(guild_id: int, enabled: bool, updated_by: int):
            return False

    class AutoRedeemChannelsAdapter(_FallbackAdapter):
        @staticmethod
        def get_channel(guild_id: int):
            return None
        
        @staticmethod
        def set_channel(guild_id: int, channel_id: int, added_by: int):
            return False

    class AutoRedeemMembersAdapter(_FallbackAdapter):
        @staticmethod
        def get_members(guild_id: int):
            return []
        @staticmethod
        def add_member(guild_id: int, fid: str, member_data: Dict[str, Any]):
            return False
        @staticmethod
        def remove_member(guild_id: int, fid: str):
            return False
        @staticmethod
        def member_exists(guild_id: int, fid: str):
            return False

    class GiftCodeRedemptionAdapter(_FallbackAdapter):
        @staticmethod
        def track_redemption(guild_id: int, code: str, fid: str, status: str):
            return False

    class AutoRedeemedCodesAdapter(_FallbackAdapter):
        @staticmethod
        def mark_code_redeemed_for_member(guild_id: int, code: str, fid: str, status: str):
            return False
        @staticmethod
        def is_redeemed(guild_id: int, code: str, fid: str):
            return False

    def _get_db():
        return None

    __all__ = [
        'mongo_enabled', 'UserTimezonesAdapter', 'BirthdaysAdapter', 'BirthdayChannelAdapter', 
        'UserProfilesAdapter', 'GiftcodeStateAdapter', 'GiftCodesAdapter', 'AllianceMembersAdapter', 
        'AutoRedeemSettingsAdapter', 'AutoRedeemChannelsAdapter', 'WelcomeChannelAdapter',
        'AutoRedeemMembersAdapter', 'GiftCodeRedemptionAdapter', 'AutoRedeemedCodesAdapter', '_get_db'
    ]


