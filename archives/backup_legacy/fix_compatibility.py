
import os
import re

def fix_file(filepath):
    print(f"Processing {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Be very aggressive with app_commands import removal
    content = re.sub(r'from discord import .*app_commands.*', '', content)
    content = re.sub(r'import discord\.app_commands', '', content)
    # Also handle commented out ones to be safe
    content = re.sub(r'# # from discord import .*app_commands.*', '', content)

    # 2. Fix decorators
    content = content.replace("@app_commands.command", "@discord.slash_command")
    content = content.replace("@discord.app_commands.command", "@discord.slash_command")
    content = content.replace("@app_commands.describe", "# @app_commands.describe")
    content = content.replace("@discord.app_commands.describe", "# @discord.app_commands.describe")
    content = content.replace("@app_commands.guild_only()", "@discord.guild_only()")
    content = content.replace("@discord.app_commands.guild_only()", "@discord.guild_only()")
    content = content.replace("@app_commands.default_permissions", "@discord.default_permissions")
    content = content.replace("@discord.app_commands.default_permissions", "@discord.default_permissions")
    content = content.replace("@app_commands.choices", "@discord.option") # Partial fix, py-cord uses options

    # 3. Fix Option and Choice types
    content = re.sub(r'discord\.OptionChoice\[.*?\]', 'discord.OptionChoice', content)
    content = re.sub(r'discord\.Option\[.*?\]', 'discord.Option', content)
    content = content.replace("discord.discord.OptionChoice", "discord.OptionChoice")
    content = content.replace("discord.app_commands.Choice", "discord.OptionChoice")
    content = content.replace("app_commands.Choice", "discord.OptionChoice")

    # 4. Fix Interaction -> ApplicationContext in function signatures
    # This is tricky because we don't want to break everything.
    # We target 'interaction: discord.Interaction' and 'interaction: Interaction'
    content = re.sub(r':\s*discord\.Interaction\b', ': discord.ApplicationContext', content)
    content = re.sub(r':\s*Interaction\b', ': discord.ApplicationContext', content)

    # 5. Fix common missing discord. prefix
    if 'import discord' in content:
        # Match Embed(...) but not discord.Embed(...)
        content = re.sub(r'(?<![a-zA-Z0-9_\.])Embed\(', 'discord.Embed(', content)
        # Match ButtonStyle. but not discord.ButtonStyle.
        content = re.sub(r'(?<![a-zA-Z0-9_\.])ButtonStyle\.', 'discord.ButtonStyle.', content)
        content = re.sub(r'(?<![a-zA-Z0-9_\.])SelectOption\(', 'discord.SelectOption(', content)
        content = re.sub(r'(?<![a-zA-Z0-9_\.])InputTextStyle\.', 'discord.InputTextStyle.', content)

    # 6. Fix wavelink.Playable
    if 'wavelink' in content:
        # content = content.replace("wavelink.Playable", "wavelink.Track")
        pass

    # 7. Fix channel_select
    content = content.replace("@discord.ui.select(cls=discord.ui.ChannelSelect", "@discord.ui.channel_select(")

    # 8. Syntax error fix for music.py specifically if needed, but let's see why it's failing.
    # The SyntaxError "unterminated string literal" often happens if a replacement inserted a newline or messed up quotes.
    
    # 9. Ensure discord import
    if 'discord.' in content and 'import discord' not in content:
        content = "import discord\n" + content

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

cogs_dir = r"f:\STARK-whiteout survival bot\DISCORD BOT\cogs"
cogs = [os.path.join(cogs_dir, f) for f in os.listdir(cogs_dir) if f.endswith('.py')]
cogs.append(r"f:\STARK-whiteout survival bot\DISCORD BOT\app.py")

for cog in cogs:
    fix_file(cog)

print("Done.")
