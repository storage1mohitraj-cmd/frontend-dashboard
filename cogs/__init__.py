"""
Package initializer for the cogs package.

This file makes the `cogs` directory an explicit Python package so imports
like `import cogs.gift_operations` work reliably, and to maintain
compatibility across different execution contexts.

It also registers a fallback module mapping so that `cogs.gift_operations`
resolves to `cogs.gift_operations_minimal` even if a top-level
`gift_operations.py` file is missing or temporarily corrupted. This keeps
older import sites working while the full implementation is developed.
"""

import importlib
import sys

__all__ = [
    "gift_operations",
    "gift_operations_minimal",
    "gift_operationsapi",
    "gift_captchasolver",
]

# Note: We do not pre-bind `cogs.gift_operations` to the minimal
# implementation here so that an actual `gift_operations.py` file in
# this package can be imported when present. The previous fallback was
# useful while the full implementation was temporarily missing, but it
# prevents replacing the module at runtime. Leave imports to Python's
# normal resolution order so the real module file is used when available.
