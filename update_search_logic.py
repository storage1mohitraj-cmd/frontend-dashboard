import io

with io.open("manage.html", "r", encoding="utf-8") as f:
    c = f.read()

replacement = """
                const filterVal = document.getElementById('preset-filter') ? document.getElementById('preset-filter').value : 'all'; 
                const searchVal = document.getElementById('preset-search') ? document.getElementById('preset-search').value.toLowerCase().trim() : '';
                let displayedPresets = REMINDER_PRESETS; 
                if (filterVal === 'mine') { 
                    displayedPresets = REMINDER_PRESETS.filter(p => p.created_by_id === _discordUserId); 
                } else if (filterVal === 'bookmarks') { 
                    displayedPresets = REMINDER_PRESETS.filter(p => BOOKMARKED_PRESETS.has(p.id)); 
                } 
                if (searchVal) {
                    displayedPresets = displayedPresets.filter(p => (p.title || '').toLowerCase().includes(searchVal) || (p.body || p.message || '').toLowerCase().includes(searchVal) || (p.created_by || '').toLowerCase().includes(searchVal));
                }
"""

c = c.replace(
    """                const filterVal = document.getElementById('preset-filter') ? document.getElementById('preset-filter').value : 'all'; 
                let displayedPresets = REMINDER_PRESETS; 
                if (filterVal === 'mine') { 
                    displayedPresets = REMINDER_PRESETS.filter(p => p.created_by_id === _discordUserId); 
                } else if (filterVal === 'bookmarks') { 
                    displayedPresets = REMINDER_PRESETS.filter(p => BOOKMARKED_PRESETS.has(p.id)); 
                }""",
    replacement.strip()
)

with io.open("manage.html", "w", encoding="utf-8") as f:
    f.write(c)

print("Updated search logic")
