import os

css_file = r"f:\Whiteout Survival Bot\frontend-dashboard\assets\site.css"

with open(css_file, 'r', encoding='utf-8') as f:
    css_content = f.read()

overrides = r"""
/* ── THIRD OVERRIDES: DESIGNER LOG, CIRCLE FAB, ONLY FRONT PAGE GRIDS ── */

/* 1. Add grids in front page only */
[data-theme="cyberpunk-cool"] .bg-animation {
  background-image: none !important; /* Removes grid from dashboard/other pages */
  opacity: 0 !important;
}
/* Ensure the front page grid is perfectly visible */
[data-theme="cyberpunk-cool"] .hero .grid-bg {
  opacity: 0.25 !important;
  display: block !important;
  background-image: 
    linear-gradient(rgba(0, 255, 255, 0.25) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 0, 255, 0.25) 1px, transparent 1px) !important;
}

/* 2. Community Chat Button MUST be a perfect circle */
[data-theme="cyberpunk-cool"] .floating-chat-fab {
  border-radius: 50% !important;
  width: 60px !important;
  height: 60px !important;
  padding: 0 !important;
  background: linear-gradient(135deg, #00FFFF, #8A2BE2) !important;
  box-shadow: 0 0 20px rgba(0, 255, 255, 0.6) !important;
  border: 2px solid #FF00FF !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  clip-path: circle(50% at 50% 50%) !important; /* Force a perfect circle shape */
}

[data-theme="cyberpunk-cool"] .floating-chat-fab:hover {
  background: linear-gradient(135deg, #FF00FF, #00BFFF) !important;
  box-shadow: 0 0 25px rgba(255, 0, 255, 0.8) !important;
  border-color: #00FFFF !important;
  transform: scale(1.1) !important;
}

/* 3. Designer System Log */
[data-theme="cyberpunk-cool"] .live-board {
  background: rgba(8, 8, 16, 0.6) !important; /* Glassmorphism base */
  border: 1px solid rgba(0, 255, 255, 0.4) !important;
  border-radius: 20px !important;
  backdrop-filter: blur(16px) !important;
  -webkit-backdrop-filter: blur(16px) !important;
  box-shadow: inset 0 0 30px rgba(0, 255, 255, 0.1), 0 0 25px rgba(255, 0, 255, 0.2) !important;
}

[data-theme="cyberpunk-cool"] .live-board::before {
  content: "CYBERPUNK NEURAL LINK" !important;
  color: #00FFFF !important;
  text-shadow: 0 0 10px rgba(0, 255, 255, 0.8) !important;
  font-family: 'Outfit', sans-serif !important;
  letter-spacing: 4px !important;
}

/* Sub-panels inside the system log */
[data-theme="cyberpunk-cool"] .status-stage,
[data-theme="cyberpunk-cool"] .event-list-panel {
  background: rgba(255, 0, 255, 0.05) !important;
  border: 1px solid rgba(255, 0, 255, 0.25) !important;
  box-shadow: inset 0 0 15px rgba(255, 0, 255, 0.1) !important;
  border-radius: 12px !important;
}

[data-theme="cyberpunk-cool"] .dispatch-bubble {
  background: rgba(0, 255, 255, 0.08) !important;
  border: 1px solid rgba(0, 255, 255, 0.2) !important;
  border-left: 4px solid #00FFFF !important;
  border-radius: 8px !important;
}

[data-theme="cyberpunk-cool"] .dispatch-bubble-title {
  color: #00FFFF !important;
  text-shadow: 0 0 5px rgba(0, 255, 255, 0.5) !important;
}

[data-theme="cyberpunk-cool"] .dispatch-bubble-time {
  color: #FF00FF !important;
}

[data-theme="cyberpunk-cool"] [data-event-title] {
  color: #00FFFF !important;
  text-shadow: 0 0 10px rgba(0, 255, 255, 0.5) !important;
}

[data-theme="cyberpunk-cool"] [data-event-message] {
  color: #ccc !important;
}
"""

css_content += overrides

with open(css_file, 'w', encoding='utf-8') as f:
    f.write(css_content)

print("Applied THIRD overrides.")
