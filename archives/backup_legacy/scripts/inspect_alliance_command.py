import sys
sys.path.append(r'F:/STARK-whiteout survival bot/DISCORD BOT')
try:
    import importlib
    mod = importlib.import_module('cogs.alliance')
    cls = getattr(mod, 'Alliance', None)
    if cls is None:
        print('Alliance class not found in cogs.alliance')
        sys.exit(1)
    from discord import app_commands
    attr = cls.__dict__.get('settings')
    print('type(settings):', type(attr))
    print('is app_commands.Command?', isinstance(attr, app_commands.Command))
    print('repr:', repr(attr))
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
