
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(r"f:\STARK-whiteout survival bot")
BACKUP_COMMIT = "37b25fc1d1d960d046bda3bcb97fa5ff1a2aa6ee"

def restore_all_py_files():
    print("Listing files in backup...")
    cmd = ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", BACKUP_COMMIT, "DISCORD_BOT_CLEAN"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error listing files: {result.stderr}")
        return

    files = result.stdout.splitlines()
    bot_root = REPO_ROOT / "DISCORD BOT"
    
    for f in files:
        if not f.endswith(".py"):
            continue
            
        # Example f: DISCORD_BOT_CLEAN/cogs/music.py
        rel_path = f.replace("DISCORD_BOT_CLEAN/", "")
        target_path = bot_root / rel_path
        
        print(f"Restoring {rel_path}...")
        try:
            cmd_show = ["git", "-C", str(REPO_ROOT), "show", f"{BACKUP_COMMIT}:{f}"]
            result_show = subprocess.run(cmd_show, capture_output=True, text=True, encoding='utf-8')
            
            if result_show.returncode == 0:
                os.makedirs(target_path.parent, exist_ok=True)
                with open(target_path, "w", encoding='utf-8') as out:
                    out.write(result_show.stdout)
            else:
                print(f"  ❌ Failed: {result_show.stderr.strip()}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    restore_all_py_files()
