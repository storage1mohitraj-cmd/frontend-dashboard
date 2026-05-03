"""
Package initializer for the cogs package in BOT 2.

Added so imports like `cogs.gift_operations` succeed when running from
the BOT 2 tree or tests that import this package directly.
"""

import importlib
import sys

__all__ = [
    "gift_operations",
    "gift_operations_minimal",
    "gift_operationsapi",
]

# Provide the same fallback mapping for BOT 2 tree so imports are robust
try:
    _minimal = importlib.import_module(f"{__name__}.gift_operations_minimal")
    sys.modules[f"{__name__}.gift_operations"] = _minimal
except Exception:
    pass
