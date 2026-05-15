import os
from datetime import datetime
import importlib
import importlib.util
import sys

# Backwards-compatible shim: try normal package import first, then fall back
# to loading the module file directly if the package path isn't importable.
try:
	from db.reminder_storage_mongo import *  # type: ignore
except Exception:
	try:
		# Resolve path to the db/reminder_storage_mongo.py file relative to this file
		base_dir = os.path.dirname(__file__)
		module_path = os.path.join(base_dir, 'db', 'reminder_storage_mongo.py')
		spec = importlib.util.spec_from_file_location('db.reminder_storage_mongo', module_path)
		if spec and spec.loader:
			module = importlib.util.module_from_spec(spec)
			# Ensure the package key exists so imports inside the module that use
			# "from db..." will resolve against sys.modules
			sys.modules['db.reminder_storage_mongo'] = module
			spec.loader.exec_module(module)
			# Re-export
			for k, v in vars(module).items():
				if not k.startswith('_'):
					globals()[k] = v
	except Exception:
		# Give up gracefully; importers will handle the absence
		pass

# Backwards-compatible shim
__all__ = ['ReminderStorageMongo']

