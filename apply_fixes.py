import os
import re
import glob

css_file = r"f:\Whiteout Survival Bot\frontend-dashboard\assets\site.css"

with open(css_file, 'r', encoding='utf-8') as f:
    css_content = f.read()

# 1. Fix Buttons
# We want to replace the current button styles for cyberpunk cool with a solid, angled, neon button
old_button_css = r"""[data-theme="cyberpunk-cool"] .btn,
[data-theme="cyberpunk-cool"] button {
  background: transparent !important;
  color: #00FFFF !important;
  border: 1px solid #FF00FF !important;
  border-radius: 4px !important;
  text-transform: uppercase;
  font-family: var(--font-mono);
  box-shadow: inset 0 0 10px rgba(255, 0, 255, 0.2), 0 0 8px rgba(0, 255, 255, 0.4) !important;
  transition: all 0.3s ease;
}

[data-theme="cyberpunk-cool"] .btn:hover,
[data-theme="cyberpunk-cool"] button:hover {
  background: rgba(255, 0, 255, 0.15) !important;
  box-shadow: inset 0 0 15px rgba(255, 0, 255, 0.4), 0 0 15px rgba(0, 255, 255, 0.8) !important;
  border-color: #00FFFF !important;
  color: #fff !important;
}"""

# New button CSS: Solid cyan/pink gradient, angled edges, intense glow
new_button_css = r"""[data-theme="cyberpunk-cool"] .btn,
[data-theme="cyberpunk-cool"] button {
  background: linear-gradient(45deg, #00FFFF, #0088FF) !important;
  color: #000 !important;
  border: none !important;
  border-radius: 0 !important;
  clip-path: polygon(12px 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%, 0 12px) !important;
  text-transform: uppercase;
  font-weight: 800;
  letter-spacing: 1px;
  font-family: 'Outfit', sans-serif;
  box-shadow: 0 0 15px rgba(0, 255, 255, 0.6) !important;
  transition: all 0.2s ease;
  padding: 10px 24px;
}

[data-theme="cyberpunk-cool"] .btn:hover,
[data-theme="cyberpunk-cool"] button:hover {
  background: linear-gradient(45deg, #FF00FF, #FF1493) !important;
  box-shadow: 0 0 25px rgba(255, 0, 255, 0.9) !important;
  color: #fff !important;
  transform: scale(1.05);
}"""

if old_button_css in css_content:
    css_content = css_content.replace(old_button_css, new_button_css)
else:
    print("Could not find old button CSS. Trying a broader regex.")
    css_content = re.sub(r'\[data-theme="cyberpunk-cool"\] \.btn,\s*\[data-theme="cyberpunk-cool"\] button\s*\{[^}]+\}\s*\[data-theme="cyberpunk-cool"\] \.btn:hover,\s*\[data-theme="cyberpunk-cool"\] button:hover\s*\{[^}]+\}', new_button_css, css_content)


# 2. Don't remove grids from front page
# Remove the rule that hides .hero-live-feed
css_content = re.sub(r'/\*\s*── CYBERPUNK COOL: Move Live Dashboard to Hero ──\s*\*/\s*\[data-theme="cyberpunk-cool"\] \.hero-live-feed\s*\{\s*display:\s*none\s*!important;\s*\}', '/* Grids preserved per user request */', css_content)

# We might also want to ensure the .grid-bg looks cool and is visible
css_content = re.sub(r'opacity:\s*0\.15;', 'opacity: 0.3;', css_content)

with open(css_file, 'w', encoding='utf-8') as f:
    f.write(css_content)
print("Updated site.css for buttons and grids.")

# 3. Fix the icon in ALL html files using regex to handle newlines
html_files = glob.glob(os.path.join(r"f:\Whiteout Survival Bot\frontend-dashboard", "**", "*.html"), recursive=True)

new_icon_html = r'<svg class="cyberpunk-cool-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'

for file_path in html_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Match the cyberpunk-cool-icon svg regardless of internal newlines/whitespace
        # It usually starts with <svg class="cyberpunk-cool-icon" and ends with </svg>
        pattern = re.compile(r'<svg\s+class="cyberpunk-cool-icon"[^>]*>.*?</svg>', re.DOTALL)
        
        new_content = pattern.sub(new_icon_html, content)
        
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Fixed icon in {file_path}")
            
    except Exception as e:
        print(f"Failed {file_path}: {e}")
