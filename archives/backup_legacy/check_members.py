import sqlite3
from pathlib import Path

# Get the database path
repo_root = Path(__file__).resolve().parent
db_path = repo_root / "db" / "users.sqlite"

print("=" * 60)
print("Database Member Check")
print("=" * 60)
print()

if not db_path.exists():
    print(f"❌ Database not found at: {db_path}")
    exit(1)

# Connect to database
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get total users
cursor.execute("SELECT COUNT(*) FROM users")
total = cursor.fetchone()[0]
print(f"📊 Total users in database: {total}")
print()

# Get members per alliance
cursor.execute("SELECT alliance, COUNT(*) FROM users GROUP BY alliance ORDER BY COUNT(*) DESC")
results = cursor.fetchall()

if results:
    print("👥 Members per alliance:")
    print("-" * 60)
    for alliance_id, count in results:
        print(f"   Alliance {alliance_id}: {count} members")
    print("-" * 60)
else:
    print("⚠️  No members found in any alliance")

print()

# Check if there are users with NULL alliance
cursor.execute("SELECT COUNT(*) FROM users WHERE alliance IS NULL")
null_count = cursor.fetchone()[0]
if null_count > 0:
    print(f"⚠️  {null_count} users have NULL alliance")

conn.close()
