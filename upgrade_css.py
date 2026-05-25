import re
import sys

file_path = r"f:\Whiteout Survival Bot\frontend-dashboard\assets\site.css"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# We only want to modify the section for Cyberpunk Cool.
# Let's find the start and end of this block.
start_marker = "CYBERPUNK COOL THEME"
end_marker = "/* Footer bottom copyright styling */"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers")
    sys.exit(1)

pre_content = content[:start_idx]
theme_content = content[start_idx:end_idx]
post_content = content[end_idx:]

# Make it better by changing general gold (255, 215, 0) and #FFD700 
# to Hot Pink (#FF00FF) and Neon Cyan (#00FFFF), but preserving yellow for headings.

# Let's do selective replacements for a vibrant Cyberpunk aesthetic:

# 1. Animations (Pulse, Glow, Scan, etc) - use Neon Cyan or Hot Pink instead of Gold
theme_content = theme_content.replace('rgba(255, 215, 0, 0.5)', 'rgba(0, 255, 255, 0.5)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.2)', 'rgba(255, 0, 255, 0.2)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.8)', 'rgba(0, 255, 255, 0.8)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.35)', 'rgba(255, 0, 255, 0.35)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.6)', 'rgba(0, 255, 255, 0.6)')
theme_content = theme_content.replace('rgba(255, 215, 0, 1)', 'rgba(0, 255, 255, 1)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.03)', 'rgba(0, 255, 255, 0.03)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.05)', 'rgba(255, 0, 255, 0.05)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.1)', 'rgba(0, 255, 255, 0.1)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.15)', 'rgba(255, 0, 255, 0.15)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.3)', 'rgba(0, 255, 255, 0.3)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.4)', 'rgba(255, 0, 255, 0.4)')
theme_content = theme_content.replace('rgba(255, 215, 0, 0.45)', 'rgba(0, 255, 255, 0.45)')

# For box-shadow and text-shadow with #FFD700
theme_content = theme_content.replace('box-shadow: 0 0 4px #FFD700', 'box-shadow: 0 0 4px #00FFFF')
theme_content = theme_content.replace('box-shadow: 0 0 8px #FFD700', 'box-shadow: 0 0 8px #00FFFF')
theme_content = theme_content.replace('border: 1px solid #FFD700', 'border: 1px solid #00FFFF')
theme_content = theme_content.replace('border: 2px solid #FFD700', 'border: 2px solid #FF00FF')

# Some general color replacements except for headings
# We will replace all #FFD700 with #00FFFF (Cyan) or #FF00FF (Pink) based on context,
# but we need to keep yellow for topic headers. 
# We can restore yellow for headers specifically.

theme_content = theme_content.replace('#FFD700', '#00FFFF')
theme_content = theme_content.replace('BLACK × GOLD × NEON', 'BLACK × NEON CYAN × HOT PINK')

# Now, restore Yellow (#FFD700) for specific heading classes to "preserve yellow only for main topics"
# We know classes like .section-heading p, .section-kicker, .page-hero p, .hero-title, .sys-info-header
restorations = [
    (r'(\[data-theme="cyberpunk-cool"\] \.section-heading p,\s*\[data-theme="cyberpunk-cool"\] \.section-kicker,\s*\[data-theme="cyberpunk-cool"\] \.page-hero p,\s*\[data-theme="cyberpunk-cool"\] \.feature-section>div>p\s*\{\s*color:\s*)#00FFFF', r'\1#FFD700'),
    (r'(\[data-theme="cyberpunk-cool"\] \.section-heading p,\s*\[data-theme="cyberpunk-cool"\] \.section-kicker,\s*\[data-theme="cyberpunk-cool"\] \.page-hero p,\s*\[data-theme="cyberpunk-cool"\] \.feature-section>div>p\s*\{[^}]*text-shadow:\s*0 0 8px\s*)rgba\(255, 0, 255, 0.4\)', r'\1rgba(255, 215, 0, 0.4)'),
    (r'(\[data-theme="cyberpunk-cool"\] \.sys-info-header\s*\{[^}]*color:\s*)#ff2a2a', r'\1#FFD700'),
    (r'(\[data-theme="cyberpunk-cool"\] \.sys-info-header\s*\{[^}]*text-shadow:\s*0 0 10px\s*)rgba\(255, 42, 42, 0.8\)', r'\1rgba(255, 215, 0, 0.8)'),
    (r'(\.cyberpunk-cool-console-title\s*\{[^}]*color:\s*)#00FFFF', r'\1#FFD700'),
]

for pat, repl in restorations:
    theme_content = re.sub(pat, repl, theme_content, flags=re.MULTILINE)

# Improve card background to be a bit more glassmorphism
theme_content = theme_content.replace('background: #080808 !important;', 'background: rgba(8, 8, 12, 0.7) !important;')
theme_content = theme_content.replace('background: #0c0c0c !important;', 'background: rgba(12, 12, 16, 0.75) !important;')
theme_content = theme_content.replace('backdrop-filter: blur(12px);', 'backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);')

# Increase intensity of hover states
theme_content = theme_content.replace('box-shadow: 0 0 20px rgba(255, 0, 255, 0.3), 0 8px 32px rgba(0, 0, 0, 0.8) !important;', 'box-shadow: 0 0 25px rgba(255, 0, 255, 0.6), 0 8px 32px rgba(0, 0, 0, 0.9) !important;')

new_content = pre_content + theme_content + post_content

if content != new_content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("CSS Upgraded.")
else:
    print("No changes made.")
