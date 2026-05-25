import os

css_file = r"f:\Whiteout Survival Bot\frontend-dashboard\assets\site.css"

with open(css_file, 'r', encoding='utf-8') as f:
    css_content = f.read()

# 1. Bring back System Log (.live-command-center) and remove Live Process (.hero-live-feed)
# We will do this by appending overrides that take precedence over the previous ones.
overrides = r"""
/* ── SECOND OVERRIDES: FIX HOVERS, CHAT FAB, SYSTEM LOG ── */

/* 1. Fix Add to Discord / Dashboard Buttons hover transparency */
[data-theme="cyberpunk-cool"] .cta-btn,
[data-theme="cyberpunk-cool"] .ghost-link,
[data-theme="cyberpunk-cool"] a.ghost-link.dashboard-cta {
  background: linear-gradient(45deg, #00FFFF, #00BFFF) !important;
  color: #000 !important;
  border: none !important;
  border-radius: 0 !important;
  clip-path: polygon(12px 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%, 0 12px) !important;
  text-transform: uppercase !important;
  font-weight: 800 !important;
  letter-spacing: 1px !important;
  font-family: 'Outfit', sans-serif !important;
  box-shadow: 0 0 15px rgba(0, 255, 255, 0.6) !important;
  transition: all 0.2s ease !important;
  padding: 10px 24px !important;
}

[data-theme="cyberpunk-cool"] .cta-btn:hover,
[data-theme="cyberpunk-cool"] .ghost-link:hover,
[data-theme="cyberpunk-cool"] a.ghost-link.dashboard-cta:hover {
  background: linear-gradient(45deg, #FF00FF, #FF1493) !important;
  box-shadow: 0 0 25px rgba(255, 0, 255, 0.9) !important;
  color: #fff !important;
  transform: scale(1.05) !important;
}

/* 2. Community Chat button should be circular */
[data-theme="cyberpunk-cool"] .floating-chat-fab {
  border-radius: 50% !important;
  clip-path: none !important; /* In case a button clip path was inherited */
  width: 60px !important;
  height: 60px !important;
  background: linear-gradient(135deg, #FF00FF, #8A2BE2) !important;
  box-shadow: 0 0 20px rgba(255, 0, 255, 0.6) !important;
  border: 2px solid #00FFFF !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

[data-theme="cyberpunk-cool"] .floating-chat-fab:hover {
  background: linear-gradient(135deg, #00FFFF, #0088FF) !important;
  box-shadow: 0 0 25px rgba(0, 255, 255, 0.8) !important;
  border-color: #FF00FF !important;
  transform: scale(1.1) !important;
}

/* 3. Bring back System Log (.live-command-center) and remove Live Process (.hero-live-feed) */
[data-theme="cyberpunk-cool"] .hero-live-feed {
  display: none !important;
}

[data-theme="cyberpunk-cool"] .live-command-center {
  display: flex !important; 
}

/* Make sure the background grid (.grid-bg) is visible */
[data-theme="cyberpunk-cool"] .hero .grid-bg {
  opacity: 0.3 !important;
  display: block !important;
}
"""

css_content += overrides

with open(css_file, 'w', encoding='utf-8') as f:
    f.write(css_content)

print("Applied CSS overrides.")
