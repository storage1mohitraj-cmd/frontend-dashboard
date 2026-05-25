with open('C:/Users/mohit/.gemini/antigravity-ide/brain/e435a276-182e-4ca2-b406-a10092954dee/.system_generated/tasks/task-76.log', 'r', encoding='utf-8') as f:
    diff_log = f.read()

lines = diff_log.split('\n')
css_lines = []
in_diff = False
for line in lines:
    if line.startswith('diff --git a/assets/site.css'):
        in_diff = True
        continue
    if line.startswith('diff --git') and in_diff:
        in_diff = False
        break
    
    if in_diff:
        if line.startswith('-') and not line.startswith('---'):
            css_lines.append(line[1:])

filtered_lines = []
in_cyberpunk = False
for line in css_lines:
    if '[data-theme="cyberpunk-cool"]' in line:
        in_cyberpunk = True
    if in_cyberpunk:
        filtered_lines.append(line)
        if line == '}':
            in_cyberpunk = False

with open(r'f:\Whiteout Survival Bot\frontend-dashboard\restored_cyberpunk.css', 'w', encoding='utf-8') as f:
    f.write('\n'.join(filtered_lines))
print(f'Restored {len(filtered_lines)} lines.')
