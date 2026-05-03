import os
import subprocess
import sys

# This is a proxy script to handle Render's default 'python app.py' command
# while keeping the source code organized in the 'DISCORD BOT' folder.

if __name__ == "__main__":
    # Ensure current directory is 'DISCORD BOT' so local imports work
    project_root = os.path.dirname(os.path.abspath(__file__))
    bot_dir = os.path.join(project_root, "DISCORD BOT")
    
    if not os.path.exists(bot_dir):
        print(f"[ROOT PROXY] Error: {bot_dir} not found.")
        sys.exit(1)
        
    os.chdir(bot_dir)
    
    # Add it to sys.path just in case
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
    
    print(f"[ROOT PROXY] Starting bot from: {os.getcwd()}")
    
    # Run the real app.py using the same interpreter
    # On Linux (Render), os.execvp is preferred as it replaces the current process
    try:
        if sys.platform == "win32":
            subprocess.run([sys.executable, "app.py"])
        else:
            # Reconstruct the command line
            python_path = sys.executable
            os.execv(python_path, [python_path, "app.py"])
    except Exception as e:
        print(f"[ROOT PROXY] Fatal error starting bot: {e}")
        sys.exit(1)
