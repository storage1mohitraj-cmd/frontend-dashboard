#!/bin/bash
# Oracle VM Discord Bot Auto-Deploy Script
# This script handles the entire deployment automatically

set -e  # Exit on any error

echo "🚀 Starting automated Discord bot deployment..."
echo "================================================"

# Update system
echo "📦 Step 1/7: Updating system packages..."
sudo dnf update -y > /dev/null 2>&1

# Install dependencies
echo "📦 Step 2/7: Installing system dependencies..."
sudo dnf install -y git python3 python3-pip python3-devel gcc gcc-c++ make nodejs npm > /dev/null 2>&1

# Install PM2
echo "📦 Step 3/7: Installing PM2..."
sudo npm install -g pm2 > /dev/null 2>&1

# Clone repository
echo "📦 Step 4/7: Cloning repository..."
mkdir -p ~/app
cd ~/app
if [ -d "bot" ]; then
    echo "   Bot directory exists, pulling latest..."
    cd bot
    git pull origin main
    cd ~/app
else
    git clone https://github.com/storage1mohitraj-cmd/WOS-BOT-1.git bot
fi

cd ~/app/bot
echo "   ✅ Repository: $(git remote get-url origin)"
echo "   ✅ Branch: $(git branch --show-current) @ $(git rev-parse --short HEAD)"

# Setup Python environment
echo "📦 Step 5/7: Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "📦 Step 6/7: Installing Python dependencies (this may take 5-10 minutes)..."
pip install --disable-pip-version-check -r requirements.txt > /dev/null 2>&1

# Save dep hash so future startups/restarts skip installation
md5sum requirements.txt | awk '{print $1}' > ~/.bot_deps_hash
echo "   ✅ Dependencies installed & hash cached (future restarts will be instant)"

# Make update script executable
chmod +x scripts/update_bot.sh 2>/dev/null || true

# Create .env file only if it doesn't already exist
# (The real .env with secrets should already be on the VM from your initial setup.
#  This block only runs on FIRST deployment to avoid losing existing config.)
echo "📦 Step 7/7: Checking environment configuration..."
if [ -f ".env" ]; then
    echo "   ✅ .env already exists — skipping (preserving existing secrets)"
else
    echo "   ⚠️  No .env found — creating template. Edit it with your real values!"
    cat > .env << 'ENVEOF'
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN_HERE
GUILD_ID_1=YOUR_GUILD_ID_1
GUILD_ID_2=YOUR_GUILD_ID_2
OPENROUTER_API_KEY_1=YOUR_OPENROUTER_KEY_1
OPENROUTER_API_KEY_2=YOUR_OPENROUTER_KEY_2
OPENROUTER_API_KEY_3=YOUR_OPENROUTER_KEY_3
OPENROUTER_MODEL=deepseek/deepseek-chat-v3.1
HUGGINGFACE_API_TOKEN=YOUR_HF_TOKEN
HUGGINGFACE_MODEL=stabilityai/stable-diffusion-xl-base-1.0
MONGO_URI=YOUR_MONGO_URI_HERE
MONGO_URI_FALLBACK=YOUR_MONGO_URI_FALLBACK_HERE
BOT_OWNER_ID=YOUR_DISCORD_USER_ID
GIFTCODE_MONITOR_CHANNEL_ID=
BIRTHDAY_NOTIFY_CHANNEL=
FEEDBACK_CHANNEL_ID=
LAVALINK_HOST=lavalinkv4.serenetia.com
LAVALINK_PORT=443
LAVALINK_PASSWORD=https://dsc.gg/ajidevserver
LAVALINK_SECURE=true
MUSIC_DEFAULT_VOLUME=50
MUSIC_MAX_QUEUE_SIZE=100
MUSIC_DISCONNECT_TIMEOUT=300
MUSIC_AUTO_RESUME=false
DEEPL_API_KEY=YOUR_DEEPL_KEY
CHROMA_ENABLED=true
GOOGLE_SHEET_ID=
ENVEOF
    echo "   ⚠️  Edit ~/.env on the VM: nano ~/app/bot/.env"
fi

# Start with PM2
echo "🚀 Starting bot with PM2..."
pm2 delete discordbot > /dev/null 2>&1 || true
pm2 start app.py \
    --name discordbot \
    --interpreter /home/opc/app/bot/venv/bin/python \
    --max-memory-restart 700M \
    --time \
    --env SKIP_INSTALL=true

# Save PM2 config
pm2 save

# Setup startup
pm2 startup > /tmp/pm2_startup.txt 2>&1
startup_cmd=$(grep "sudo env" /tmp/pm2_startup.txt | head -1)
if [ ! -z "$startup_cmd" ]; then
    eval "$startup_cmd"
fi

echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo "================================================"
echo ""
pm2 list
echo ""
echo "📊 Check logs with: pm2 logs discordbot"
echo "🔄 Restart with: pm2 restart discordbot"
echo "📈 Monitor with: pm2 monit"
echo ""
echo "🎉 Your bot should now be online in Discord!"
