import os
import glob
import re

search_dir = r"f:\Whiteout Survival Bot\frontend-dashboard"
extensions = ["*.html", "*.js"]
files = []

for ext in extensions:
    files.extend(glob.glob(os.path.join(search_dir, "**", ext), recursive=True))

old_script = r"const savedTheme = localStorage.getItem('theme') || 'cyberpunk-cool';"
new_script = r"""let savedTheme = localStorage.getItem('theme') || 'cyberpunk-cool';
    if (savedTheme === 'viper') {
      savedTheme = 'cyberpunk-cool';
      localStorage.setItem('theme', 'cyberpunk-cool');
    }"""

old_script_js = r"const initTheme = localStorage.getItem('theme') || 'dark';"
new_script_js = r"""let initTheme = localStorage.getItem('theme') || 'dark';
    if (initTheme === 'viper') {
      initTheme = 'cyberpunk-cool';
      localStorage.setItem('theme', 'cyberpunk-cool');
    }"""

old_icon = r'<svg class="cyberpunk-cool-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor"><path d="M12 2C6 2 2 7 2 12s4 10 10 10 10-4.5 10-10S18 2 12 2z" stroke-width="1.5"/><path d="M12 8v4l3 3" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="2" fill="currentColor" stroke="none"/></svg>'
new_icon = r'<svg class="cyberpunk-cool-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'

for file_path in files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        new_content = content
        
        # Replace the savedTheme variable in HTML files
        new_content = new_content.replace(old_script, new_script)
        
        # In heroes.html and some others there are `const currentTheme = localStorage.getItem('theme') || 'cyberpunk-cool';`
        new_content = new_content.replace(
            "const currentTheme = localStorage.getItem('theme') || 'cyberpunk-cool';",
            "let currentTheme = localStorage.getItem('theme') || 'cyberpunk-cool'; if (currentTheme === 'viper') { currentTheme = 'cyberpunk-cool'; localStorage.setItem('theme', 'cyberpunk-cool'); }"
        )
        
        # Site.js initTheme
        new_content = new_content.replace(old_script_js, new_script_js)
        
        # Update Icon
        new_content = new_content.replace(old_icon, new_icon)

        if content != new_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Fixed {file_path}")
    except Exception as e:
        print(f"Failed to process {file_path}: {e}")
