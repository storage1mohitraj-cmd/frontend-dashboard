---
description: Push all changes to GitHub and auto-deploy to Oracle VM
---

# Push & Deploy Workflow

This workflow MUST be run automatically after every session where code changes are made to the bot — no user prompt needed. When the user says "make changes", "fix X", "add Y", etc., run this at the end.

## Pre-conditions
- Working directory: `f:\Whiteout Survival Bot`
- Git remote: `origin` → `https://github.com/storage1mohitraj-cmd/WOS-BOT-1.git`
- GitHub Actions auto-deploys to Oracle VM on every push to `main`

---

## Steps

### 1. Check git status
// turbo
```
cd "f:\Whiteout Survival Bot" && git status
```

### 2. Stage all changes
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

# Commit for dashboard (if needed)
if (Test-Path "f:\Whiteout Survival Bot\frontend-dashboard\.git") {
    cd "f:\Whiteout Survival Bot\frontend-dashboard"
    git commit -m "feat: <description>"
}
```
If nothing to commit (clean tree), skip steps 3 and 4.

### 4. Push to GitHub (triggers auto-deploy to Oracle VM)
// turbo
```powershell
# Push main bot repo
cd "f:\Whiteout Survival Bot" && git push origin main

# Push frontend-dashboard repo (if it exists and has changes)
if (Test-Path "f:\Whiteout Survival Bot\frontend-dashboard\.git") {
    cd "f:\Whiteout Survival Bot\frontend-dashboard"
    git add -A
    git commit -m "chore: sync with main repo changes"
    git push origin main
}
```

### 5. Instant Deploy via SSH
Bypasses the 2-minute GitHub Actions wait by pushing directly to the VM.
// turbo
```
ssh -i "C:\Users\mohit\.ssh\oracle_vm_key" -o StrictHostKeyChecking=no ubuntu@140.245.241.54 "cd bot && git pull && pm2 restart discordbot"
```

### 6. Confirm Deployment
After a successful SSH restart:
- ✅ Changes pushed to GitHub
- 🚀 Instant SSH Deploy successful
- 🔄 Bot restarted on Oracle VM (Ubuntu)
- The bot is now LIVE with the new changes!
