import os
import glob

base_dir = r"f:\Whiteout Survival Bot\frontend-dashboard"
html_files = glob.glob(os.path.join(base_dir, "*.html"))

for file in html_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '[data-theme="cyberpunk-cool"] {' in content:
        start_idx = content.find('[data-theme="cyberpunk-cool"] {')
        end_idx = content.find('@keyframes cartoonBgShift')
        if end_idx == -1:
             end_idx = content.find('[data-theme="cartoon"] {')
        if end_idx == -1:
             end_idx = content.find('</style>')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            new_css = """[data-theme="cyberpunk-cool"] {
      --radius: 8px;
      --bg-dark: #030712;
      --card-bg: rgba(17, 24, 39, 0.7);
      --glass-border: rgba(255, 255, 255, 0.05);
      --text-main: #f9fafb;
      --text-muted: #9ca3af;
      --primary: #6366f1;
      --gradient-brand: linear-gradient(135deg, #fff 0%, #9ca3af 100%);
    }

    """
            content = content[:start_idx] + new_css + content[end_idx:]
            with open(file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {file}")

site_css_path = os.path.join(base_dir, "assets", "site.css")
with open(site_css_path, 'r', encoding='utf-8') as f:
    site_css = f.read()

lines = site_css.split('\n')
filtered_lines = []
in_cyberpunk_block = False
brace_count = 0

for line in lines:
    if not in_cyberpunk_block:
        if '[data-theme="cyberpunk-cool"]' in line and '{' in line:
            in_cyberpunk_block = True
            brace_count = line.count('{') - line.count('}')
            if brace_count <= 0:
                in_cyberpunk_block = False
                brace_count = 0
        elif '[data-theme="cyberpunk-cool"]' in line and ',' in line:
            in_cyberpunk_block = True
            brace_count = line.count('{') - line.count('}')
            if brace_count <= 0 and '{' in line:
                in_cyberpunk_block = False
                brace_count = 0
        else:
            filtered_lines.append(line)
    else:
        if '{' in line:
            brace_count += line.count('{')
        if '}' in line:
            brace_count -= line.count('}')
            if brace_count <= 0:
                in_cyberpunk_block = False
                brace_count = 0

new_site_css = '\n'.join(filtered_lines)

with open(site_css_path, 'w', encoding='utf-8') as f:
    f.write(new_site_css)
print("Updated site.css")

