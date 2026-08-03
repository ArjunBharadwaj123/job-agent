"""
One-shot schema initializer. Applies schema.sql to the configured libSQL
database (idempotent). Run: PYTHONPATH=src python src/init_db.py
"""

import store


def main():
    conn = store.init_schema()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print("Schema applied. Tables:", [t[0] for t in tables])


if __name__ == "__main__":
    main()
