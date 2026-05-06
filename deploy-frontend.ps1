# deploy-frontend.ps1
# Robust deployment system for Whiteout Survival Dashboard

param (
    [string]$CommitMessage = "Update dashboard"
)

Write-Host "🚀 Starting Frontend Deployment..." -ForegroundColor Cyan

# 1. Stage changes
Write-Host "📦 Staging changes..." -ForegroundColor Yellow
git add frontend-dashboard/

# 2. Commit
Write-Host "📝 Committing changes..." -ForegroundColor Yellow
git commit -m "feat(frontend): $CommitMessage"

# 3. Push to Main Bot Repo (Backup/History)
Write-Host "📤 Pushing to main bot repo (origin)..." -ForegroundColor Yellow
git push origin main

# 4. Push to Dedicated Frontend Repo (FAST)
Write-Host "📤 Pushing to dedicated frontend repo (magnus-1234/frontend-dashboard)..." -ForegroundColor Yellow
# Using direct push from nested repo for speed
cd "f:\Whiteout Survival Bot\frontend-dashboard"
git add -A
git commit -m "feat: $CommitMessage"
git push origin main
cd "f:\Whiteout Survival Bot"

# 5. Deploy to Oracle VM (Backend/API Sync)
Write-Host "🔄 Syncing with Oracle VM..." -ForegroundColor Yellow
ssh -i "C:\Users\mohit\.ssh\oracle_vm_key" -o StrictHostKeyChecking=no ubuntu@140.245.241.54 "cd bot && git pull && pm2 restart discordbot"

Write-Host "✨ Frontend deployment complete!" -ForegroundColor Green
