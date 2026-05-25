import os
import glob

search_dir = r"f:\Whiteout Survival Bot\frontend-dashboard"
extensions = ["*.html", "*.js", "*.css"]
files = []

for ext in extensions:
    files.extend(glob.glob(os.path.join(search_dir, "**", ext), recursive=True))

for file_path in files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Perform replacements
        new_content = content.replace("viper", "cyberpunk-cool")
        new_content = new_content.replace("Viper", "Cyberpunk Cool")
        new_content = new_content.replace("VIPER", "CYBERPUNK COOL")

        if content != new_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {file_path}")
    except Exception as e:
        print(f"Failed to process {file_path}: {e}")
