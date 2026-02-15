# 🏠 Self-Hosting Guide - Run Bot on Your PC 24/7

## ✅ Why Self-Host?
- **FREE forever** - No hosting costs
- **Clean IP** - Your home internet has good reputation
- **No rate limits** - Discord won't ban your home IP
- **Full control** - No platform restrictions

---

## 🚀 Quick Start (Simple Method)

### 1. Run Bot Manually
```powershell
cd "f:\Whiteout Survival Bot\DISCORD BOT"
python app.py
```

**Keep the window open** - Bot runs as long as terminal is open.

---

## ⚙️ Advanced Setup (Auto-Start on Boot)

### 1. Install as Windows Service

**Right-click** `install_service.bat` → **Run as Administrator**

This will:
- Download NSSM (service manager)
- Install bot as Windows service
- Set it to auto-start on boot
- Start the bot immediately

### 2. Manage the Service

```powershell
# Check status
nssm.exe status WOSBot

# Stop bot
nssm.exe stop WOSBot

# Start bot
nssm.exe start WOSBot

# Restart bot
nssm.exe restart WOSBot

# Remove service (if needed)
nssm.exe remove WOSBot confirm
```

---

## 🔧 Configuration

### Keep Your PC Online
The bot only runs when your PC is on. To maximize uptime:

1. **Disable Sleep Mode**:
   - Settings → System → Power → Screen and sleep
   - Set both to "Never"

2. **Prevent Auto Updates**:
   - Settings → Windows Update → Advanced options
   - Schedule updates for specific times

3. **Optional: Wake-on-LAN**:
   - Enable in BIOS to remotely wake PC if it shuts down

### Monitor the Bot

Check logs in real-time:
```powershell
# View service logs
nssm.exe status WOSBot
```

Or check Windows Event Viewer:
- Open Event Viewer → Applications and Services Logs

---

## 🐛 Troubleshooting

### Bot Won't Start
```powershell
# Check Python path
where python

# Check if port is already in use
netstat -ano | findstr "8080"

# View detailed error logs
nssm.exe status WOSBot
```

### Fix Missing Animation Files
The warning about `thinking_animation.json` is **harmless**. To fix:
```powershell
mkdir animations
# Bot will create the file automatically on next run
```

### Unclosed Client Session Warning
This is **cosmetic** and doesn't affect functionality. Ignore it.

---

## 📊 Performance Tips

### Reduce Resource Usage
- Close unnecessary programs
- Use Task Manager to monitor CPU/RAM
- Bot typically uses ~100-200MB RAM

### Network Considerations
- Bot uses minimal bandwidth (~1-5 MB/hour)
- Won't affect gaming/streaming
- Open port 8080 in firewall if needed

---

## 🔒 Security

### Protect Your Token
- Never share `.env` file
- Keep `DISCORD_TOKEN` secret
- Don't push `.env` to GitHub

### Firewall Rules
Bot doesn't need incoming connections (only outgoing to Discord). No port forwarding needed.

---

## ✅ You're Done!

Your bot is now running on your PC 24/7 with:
- ✅ No rate limits (clean home IP)
- ✅ No hosting costs
- ✅ Auto-start on boot
- ✅ Full control

**Need help?** Check logs or restart the service.
