---
description: Push all changes to GitHub and auto-deploy to Oracle VM
---

# Push & Deploy Workflow

This workflow MUST be run automatically after every session where code changes are made to the bot — no user prompt needed. When the user says "make changes", "fix X", "add Y", etc., run this at the end.

## Pre-conditions
- Working directory: `f:\Whiteout Survival Bot`
- Main Bot git remote: `origin` → `https://github.com/storage1mohitraj-cmd/WOS-BOT-1.git`
- Frontend Dashboard git remote: `origin` → `https://github.com/magnus-1234/frontend-dashboard.git`
- GitHub Actions auto-deploys to Oracle VM on every push to `main`

---

## Steps

### 1. Check git status for both repos
// turbo
```powershell
cd "f:\Whiteout Survival Bot"; git status
if (Test-Path "f:\Whiteout Survival Bot\frontend-dashboard\.git") {
    cd "f:\Whiteout Survival Bot\frontend-dashboard"; git status
}
```

### 2. Stage all changes in both repos
// turbo
```powershell
cd "f:\Whiteout Survival Bot" && git add -A
if (Test-Path "f:\Whiteout Survival Bot\frontend-dashboard\.git") {
    cd "f:\Whiteout Survival Bot\frontend-dashboard" && git add -A
}
```

### 3. Commit with a descriptive message (summarize what changed)
Use a commit message that describes the actual change made:
```powershell
# Commit for main repo
cd "f:\Whiteout Survival Bot"
git commit -m "feat: <description>"

# Commit for dashboard
if (Test-Path "f:\Whiteout Survival Bot\frontend-dashboard\.git") {
    cd "f:\Whiteout Survival Bot\frontend-dashboard"
    git commit -m "feat: <description>"
}
```
If nothing to commit (clean tree), skip steps 3 and 4.

### 4. Push to GitHub for both repos (triggers auto-deploy to Oracle VM)
// turbo
```powershell
# Push main bot repo
cd "f:\Whiteout Survival Bot" && git push origin main

# Push frontend-dashboard repo
if (Test-Path "f:\Whiteout Survival Bot\frontend-dashboard\.git") {
    cd "f:\Whiteout Survival Bot\frontend-dashboard" && git push origin main
}
```

### 5. Instant Deploy via SSH (Updates both bot and frontend on the VM)
Bypasses the 2-minute GitHub Actions wait by pushing directly to the VM.
// turbo
```powershell
ssh -i "C:\Users\mohit\.ssh\oracle_vm_key" -o StrictHostKeyChecking=no ubuntu@140.245.241.54 "cd bot && git pull && cd frontend-dashboard && git pull && pm2 restart discordbot"
```

### 6. Confirm Deployment
After a successful SSH restart:
- ✅ Changes pushed to GitHub (both Main Bot and Frontend Dashboard)
- 🚀 Instant SSH Deploy successful (both repositories pulled on VM)
- 🔄 Bot restarted on Oracle VM (Ubuntu)
- The bot and frontend dashboard are now LIVE with the new changes!
