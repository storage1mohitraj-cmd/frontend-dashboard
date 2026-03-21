// PM2 Ecosystem Configuration
// Usage (Oracle VM):
//   pm2 start ecosystem.config.js
//   pm2 save
//   pm2 startup   # auto-start on VM reboot
//
// Key settings that prevent the outage restart loop:
//   max_restarts  – stop respawning after 5 crashes (prevents infinite crash loop)
//   restart_delay – wait 30 s before each restart (avoids hammering Discord gateway)
//   kill_timeout  – give the old process 15 s to die before PM2 starts the new one
//                   (prevents the "ExtensionAlreadyLoaded" duplicate-cog errors)
//   watch: false  – never restart just because a file changed

module.exports = {
  apps: [
    {
      name: "discordbot",
      script: "app.py",
      interpreter: "python3",   // change to "python" on Windows
      cwd: "/home/opc/app/bot/DISCORD BOT",  // Oracle VM path

      // ── Restart policy ──────────────────────────────────────────────────
      max_restarts: 5,           // hard-stop loop after 5 consecutive crashes
      restart_delay: 30000,     // 30 s cool-down between restarts
      min_uptime: "60s",        // a run shorter than 60 s counts as a crash
      kill_timeout: 15000,      // 15 s for graceful shutdown before SIGKILL

      // ── Process behaviour ───────────────────────────────────────────────
      watch: false,              // don't restart on file changes
      autorestart: true,         // do restart on actual crashes (exit code ≠ 0)

      // ── Environment variables ───────────────────────────────────────────
      env: {
        // Skips pip install on every start → removes 1–3 min startup gap.
        // Only set to false when you explicitly upgrade requirements.txt.
        SKIP_INSTALL: "true",

        // Oracle VM: 8080 is normally fine; Render uses PORT env var.
        PORT: "8080",

        PYTHONUNBUFFERED: "1",   // ensures logs appear immediately
      },

      // ── Log files ───────────────────────────────────────────────────────
      out_file: "/home/opc/app/bot/discordbot-out.log",
      error_file: "/home/opc/app/bot/discordbot-error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: false,
    },
  ],
};
