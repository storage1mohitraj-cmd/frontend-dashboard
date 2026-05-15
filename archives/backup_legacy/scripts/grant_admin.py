import os
import sys
import sqlite3

def grant_admin(user_id: int):
    try:
        from db.mongo_adapters import AdminsAdapter, mongo_enabled
    except Exception:
        AdminsAdapter = None
        def mongo_enabled():
            return False

    if mongo_enabled() and AdminsAdapter:
        try:
            ok = AdminsAdapter.upsert(user_id, 1)
            doc = AdminsAdapter.get(user_id)
            print(f"Mongo upsert: {ok} doc: {doc}")
        except Exception as e:
            print(f"Mongo operation error: {e}")
    else:
        print('Mongo not configured (MONGO_URI missing)')

    os.makedirs('db', exist_ok=True)
    conn = sqlite3.connect('db/settings.sqlite')
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY, is_initial INTEGER DEFAULT 0)")
    cur.execute("INSERT OR REPLACE INTO admin (id, is_initial) VALUES (?, 1)", (user_id,))
    conn.commit()
    cur.execute("SELECT id, is_initial FROM admin WHERE id = ?", (user_id,))
    row = cur.fetchone()
    print(f"SQLite admin row: {row}")
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python grant_admin.py <discord_user_id>')
        sys.exit(1)
    try:
        uid = int(sys.argv[1])
    except ValueError:
        print('Invalid user id; must be integer')
        sys.exit(1)
    grant_admin(uid)