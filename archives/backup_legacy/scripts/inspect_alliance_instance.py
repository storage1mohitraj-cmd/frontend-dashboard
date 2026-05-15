import sys
sys.path.append(r'F:/STARK-whiteout survival bot/DISCORD BOT')
import importlib, sqlite3
mod = importlib.import_module('cogs.alliance')
cls = mod.Alliance
conn = sqlite3.connect('F:/STARK-whiteout survival bot/DISCORD BOT/db/alliance.sqlite')
inst = cls(None, conn)
from discord import app_commands
inst_attr = getattr(inst, 'settings')
print('instance.settings type:', type(inst_attr))
print('is app_commands.Command?', isinstance(inst_attr, app_commands.Command))
print('repr:', repr(inst_attr))
