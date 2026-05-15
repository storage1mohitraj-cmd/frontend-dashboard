#!/usr/bin/env python3
"""Migrate SQLite files under `db/` into MongoDB collections.

Usage examples:
  python tools/migrate_sqlite_to_mongo.py            # scans db/ and imports into target DB
  python tools/migrate_sqlite_to_mongo.py --files db/giftcode.sqlite db/alliance.sqlite --drop

Collections will be named <sqlite_filename_no_ext>__<table_name> by default.
By default the target MongoDB database is taken from MONGO_DB_NAME env or 'sqlite_imports'.

The script uses `db.mongo_client_wrapper.get_mongo_client` so it honors your existing MONGO_URI
environment and connection retry settings.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
import os
import sys
from typing import Iterable
from datetime import datetime

# Ensure repository root is on sys.path so `import db.*` works when running
# this script from the tools/ directory.
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from db.mongo_client_wrapper import get_mongo_client
except Exception as e:
    print("Failed to import get_mongo_client from db.mongo_client_wrapper:", e)
    print("Run this script from the repository root so imports resolve correctly.")
    raise


def iter_sqlite_files(paths: Iterable[str] | None, db_dir: Path) -> Iterable[Path]:
    if paths:
        for p in paths:
            yield Path(p)
    else:
        for p in sorted(db_dir.glob('*.sqlite*')):
            yield p


def list_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [r[0] for r in cur.fetchall()]


def chunked(iterable, size=1000):
    it = iter(iterable)
    while True:
        chunk = []
        try:
            for _ in range(size):
                chunk.append(next(it))
        except StopIteration:
            if chunk:
                yield chunk
            break
        yield chunk


def convert_row(row: sqlite3.Row) -> dict:
    d = {}
    for k in row.keys():
        v = row[k]
        # convert bytes to hex to preserve content safely
        if isinstance(v, (bytes, bytearray)):
            try:
                d[k] = v.decode('utf-8')
            except Exception:
                d[k] = v.hex()
        elif isinstance(v, str):
            s = v.strip()
            # Attempt to detect ISO 8601-like strings and convert to datetime
            # Handle trailing Z (Zulu) by replacing with +00:00 for fromisoformat
            try:
                # quick heuristic: look for date-like patterns
                if (('T' in s and '-' in s) or (len(s) >= 10 and s.count('-') == 2 and (':' in s or ' ' in s))):
                    iso = s
                    if iso.endswith('Z'):
                        iso = iso[:-1] + '+00:00'
                    try:
                        dt = datetime.fromisoformat(iso)
                        d[k] = dt
                    except Exception:
                        # not ISO-parsable, keep original string
                        d[k] = v
                else:
                    d[k] = v
            except Exception:
                d[k] = v
        else:
            d[k] = v
    return d


def import_sqlite_file(sqlite_path: Path, client, target_db: str, drop: bool = False, dry_run: bool = False):
    sqlite_name = sqlite_path.stem
    print(f"Importing {sqlite_path} -> mongo DB '{target_db}' (prefix: {sqlite_name})")
    if not sqlite_path.exists():
        print("  file not found, skipping")
        return

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        tables = list_tables(conn)
        if not tables:
            print("  no tables found, skipping")
            return

        db = client[target_db]
        for table in tables:
            coll_name = f"{sqlite_name}__{table}"
            coll = db[coll_name]
            print(f"  table: {table} -> collection: {coll_name}")
            if drop:
                if not dry_run:
                    coll.drop()
                print("    (dropped existing collection)")

            cur = conn.cursor()
            cur.execute(f"SELECT * FROM '{table}'")
            rows = cur.fetchall()
            total = len(rows)
            print(f"    rows: {total}")

            if dry_run:
                continue

            if total == 0:
                continue

            # insert in chunks to avoid huge memory spikes
            inserted = 0
            for chunk in chunked(rows, size=1000):
                docs = [convert_row(r) for r in chunk]
                # preserve original rowid as _sqlite_rowid if present
                try:
                    res = coll.insert_many(docs)
                    inserted += len(res.inserted_ids)
                except Exception as e:
                    print(f"    insert_many failed: {e}")
                    # try one-by-one
                    for doc in docs:
                        try:
                            coll.insert_one(doc)
                            inserted += 1
                        except Exception as ee:
                            print(f"      failed to insert doc: {ee}")
            print(f"    inserted: {inserted}")
    finally:
        conn.close()


def main(argv=None):
    p = argparse.ArgumentParser(description='Migrate SQLite files to MongoDB')
    p.add_argument('--db-dir', default='db', help='Directory containing sqlite files (default: db)')
    p.add_argument('--mongo-uri', help='MongoDB URI (optional). If not provided, the script will look for MONGO_URI env var or a mongo_uri.txt file in the repo root.')
    p.add_argument('--files', nargs='+', help='Specific sqlite files to import (default: all in db/)')
    p.add_argument('--target-db', default=os.getenv('MONGO_DB_NAME', 'sqlite_imports'), help='Target MongoDB database name')
    p.add_argument('--drop', action='store_true', help='Drop existing collections before inserting')
    p.add_argument('--dry-run', action='store_true', help='Do everything except write to MongoDB')
    args = p.parse_args(argv)

    db_dir = Path(args.db_dir)

    # Determine Mongo URI: CLI arg > env var > repo mongo_uri.txt
    mongo_uri = None
    if args.mongo_uri:
        mongo_uri = args.mongo_uri
    elif os.getenv('MONGO_URI'):
        mongo_uri = os.getenv('MONGO_URI')
    else:
        # look for mongo_uri.txt at repo root
        repo_root = Path(__file__).resolve().parent.parent
        local = repo_root / 'mongo_uri.txt'
        if local.exists():
            try:
                text = local.read_text(encoding='utf-8').strip()
                if text:
                    mongo_uri = text
            except Exception:
                pass

    try:
        client = get_mongo_client(mongo_uri)
    except Exception as e:
        print('Failed to connect to MongoDB:', e)
        print('Set MONGO_URI environment variable, provide --mongo-uri, or create a mongo_uri.txt file at the repo root containing the URI.')
        sys.exit(2)

    files = list(iter_sqlite_files(args.files, db_dir))
    if not files:
        print('No sqlite files found to import')
        return

    for f in files:
        import_sqlite_file(f, client, args.target_db, drop=args.drop, dry_run=args.dry_run)


if __name__ == '__main__':
    main()

