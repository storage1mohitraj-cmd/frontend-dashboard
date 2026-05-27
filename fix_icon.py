import io

with io.open("f:\\Whiteout Survival Bot\\frontend-dashboard\\manage.html", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("setIcon('key', '#10b981'", "setIcon('unlock', '#34d399'")

with io.open("f:\\Whiteout Survival Bot\\frontend-dashboard\\manage.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Replaced successfully")
