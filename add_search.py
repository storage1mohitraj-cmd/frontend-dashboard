import io

with io.open("manage.html", "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace(
    '<select id="preset-filter"',
    '<input id="preset-search" class="form-input" type="search" placeholder="Search presets..." oninput="renderReminderPresets()" style="padding:6px 12px; font-size:0.85rem; min-width:200px;">\n                        <select id="preset-filter"'
)

with io.open("manage.html", "w", encoding="utf-8") as f:
    f.write(c)

print("Added search UI")
