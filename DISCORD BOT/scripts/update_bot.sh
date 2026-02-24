#!/bin/bash
# ============================================================
# WOS Bot — Manual Update Script (run on Oracle VM)
# Usage:
#   ./scripts/update_bot.sh           # Smart update (skip pip if reqs unchanged)
#   ./scripts/update_bot.sh --force   # Force reinstall all dependencies
# ============================================================
set -e

BOT_DIR="$HOME/app/bot"
VENV_DIR="$BOT_DIR/venv"
CACHE_FILE="$HOME/.bot_deps_hash"

cd "$BOT_DIR"

echo "================================================"
echo "🤖 WOS Bot Manual Update — $(date)"
echo "================================================"

# Pull latest code
echo ""
echo "📥 Pulling latest code from GitHub..."
git fetch origin main
OLD_HASH=$(git rev-parse --short HEAD)
git reset --hard origin/main
NEW_HASH=$(git rev-parse --short HEAD)

if [ "$OLD_HASH" = "$NEW_HASH" ]; then
  echo "ℹ️  Already up to date ($(git log -1 --pretty=%s))"
else
  echo "✅ Updated: $OLD_HASH → $NEW_HASH — $(git log -1 --pretty=%s)"
fi

# Check if requirements changed or --force passed
FORCE_INSTALL=false
if [ "$1" = "--force" ]; then
  FORCE_INSTALL=true
  echo ""
  echo "⚠️  --force flag: will reinstall all dependencies"
fi

# Compare requirements hash
CURRENT_HASH=""
if [ -f "requirements.txt" ]; then
  CURRENT_HASH=$(md5sum requirements.txt | awk '{print $1}')
fi

SAVED_HASH=""
if [ -f "$CACHE_FILE" ]; then
  SAVED_HASH=$(cat "$CACHE_FILE")
fi

if [ "$FORCE_INSTALL" = "true" ] || [ "$CURRENT_HASH" != "$SAVED_HASH" ] && [ -n "$CURRENT_HASH" ]; then
  echo ""
  echo "📦 Installing/updating Python dependencies..."
  if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    pip install --disable-pip-version-check -r requirements.txt
    echo "$CURRENT_HASH" > "$CACHE_FILE"
    echo "✅ Dependencies installed & cache updated"
  else
    echo "⚠️  venv not found at $VENV_DIR"
    echo "Run deploy_oracle.sh to set up the environment first."
    exit 1
  fi
else
  echo ""
  echo "⚡ Requirements unchanged — skipping pip install"
fi

# Restart with PM2
echo ""
echo "🔄 Restarting bot..."
if pm2 describe discordbot > /dev/null 2>&1; then
  pm2 restart discordbot --update-env
  echo "✅ Bot restarted"
else
  echo "⚠️  'discordbot' not in PM2, starting fresh..."
  pm2 start app.py \
    --name discordbot \
    --interpreter "$VENV_DIR/bin/python" \
    --max-memory-restart 700M \
    --time
  pm2 save
fi

echo ""
pm2 list
echo ""
echo "📋 Tail logs: pm2 logs discordbot --lines 30"
echo "================================================"
echo "✅ Update complete!"
echo "================================================"
