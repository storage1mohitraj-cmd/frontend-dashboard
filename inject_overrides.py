import os

css_file = r"f:\Whiteout Survival Bot\frontend-dashboard\assets\site.css"

with open(css_file, 'r', encoding='utf-8') as f:
    css_content = f.read()

# Append overrides to the very end of site.css to ensure they take precedence
overrides = r"""

/* ── USER FEEDBACK OVERRIDES ── */
/* 1. Ensure Cyberpunk buttons look good */
[data-theme="cyberpunk-cool"] .btn,
[data-theme="cyberpunk-cool"] button {
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
}

[data-theme="cyberpunk-cool"] .btn:hover,
[data-theme="cyberpunk-cool"] button:hover {
  background: linear-gradient(45deg, #FF00FF, #FF1493) !important;
  box-shadow: 0 0 25px rgba(255, 0, 255, 0.9) !important;
  color: #fff !important;
  transform: scale(1.05) !important;
}

/* 2. Don't remove grids from front page */
[data-theme="cyberpunk-cool"] .hero-live-feed {
  display: flex !important;
}

[data-theme="cyberpunk-cool"] .live-command-center {
  display: none !important; /* Hide the fake console so the grids can be seen clearly */
}

/* Make sure the background grid is visible */
[data-theme="cyberpunk-cool"] .hero .grid-bg {
  opacity: 0.3 !important;
}
"""

if "USER FEEDBACK OVERRIDES" not in css_content:
    css_content += overrides
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(css_content)
    print("Injected CSS overrides.")
else:
    print("Overrides already present.")
