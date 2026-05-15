import subprocess
import sys
import os
from pathlib import Path

# Ensure repository root is on sys.path so imports like `db.mongo_adapters`
# work correctly in deployment environments (Render may set a different CWD).
repo_root = str(Path(__file__).resolve().parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
import pprint

# Startup debug: print working directory and a short sys.path preview so
# Render logs can confirm the process cwd and import paths. This is
# temporary and can be removed after debugging.
try:
    print("STARTUP DEBUG: CWD=", os.getcwd())
    print("STARTUP DEBUG: sys.path (first 6 entries)=")
    pprint.pprint(sys.path[:6])
    # Print whether key env vars exist (don't print values)
    print("STARTUP DEBUG: MONGO_URI set?", bool(os.getenv('MONGO_URI')))
    print("STARTUP DEBUG: DEV_GUILD_ID set?", bool(os.getenv('DEV_GUILD_ID')))
except Exception as _:
    pass
# Try to ensure `db.mongo_adapters` is importable in environments where
# the package wasn't installed (e.g., Render builds without `pip install -e .`).
try:
    import db.mongo_adapters  # noqa: F401
except Exception:
    try:
        import importlib.util
        import types

        db_pkg_name = 'db'
        # Ensure a `db` package object exists in sys.modules
        if db_pkg_name not in sys.modules:
            pkg = types.ModuleType(db_pkg_name)
            pkg.__path__ = [os.path.join(repo_root, 'db')]
            sys.modules[db_pkg_name] = pkg

        # Attempt to load the module file directly from the repo
        module_path = os.path.join(repo_root, 'db', 'mongo_adapters.py')
        if os.path.exists(module_path):
            spec = importlib.util.spec_from_file_location('db.mongo_adapters', module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore
            sys.modules['db.mongo_adapters'] = module
            print('STARTUP DEBUG: loaded db.mongo_adapters from file')
        else:
            print('STARTUP DEBUG: db.mongo_adapters file not found at', module_path)
    except Exception as e:
        print('STARTUP DEBUG: failed to load db.mongo_adapters:', e)
import shutil
import stat

def is_container() -> bool:
    return os.path.exists("/.dockerenv") or os.path.exists("/var/run/secrets/kubernetes.io")

def is_ci_environment() -> bool:
    """Check if running in a CI environment"""
    ci_indicators = [
        'CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS', 
        'JENKINS_URL', 'TRAVIS', 'CIRCLECI', 'GITLAB_CI'
    ]
    return any(os.getenv(indicator) for indicator in ci_indicators)

def should_skip_venv() -> bool:
    """Check if venv should be skipped"""
    return '--no-venv' in sys.argv or is_container() or is_ci_environment()

# (Remaining content preserved from original main.py...)
