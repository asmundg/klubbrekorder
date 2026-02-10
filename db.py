import sqlite3
from pathlib import Path

from main import ClubRecord, parse_result_value

DEFAULT_DB_PATH = Path("records.db")

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    age_class TEXT NOT NULL,
    event TEXT NOT NULL,
    name TEXT NOT NULL,
    result TEXT NOT NULL,
    result_value REAL NOT NULL,
    year INTEGER NOT NULL,
    indoor INTEGER NOT NULL DEFAULT 0,
    UNIQUE(source, age_class, event, name, result, year, indoor)
);
"""


def init_db(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def insert_records(conn: sqlite3.Connection, records: list[ClubRecord], source: str) -> int:
    """Insert records into the database (INSERT OR IGNORE for idempotency). Returns count inserted."""
    count = 0
    for r in records:
        try:
            result_val = parse_result_value(r.result)
        except (ValueError, IndexError):
            print(f"  WARNING: skipping unparseable result: {r.event} {r.result}")
            continue
        cursor = conn.execute(
            "INSERT OR IGNORE INTO records (source, age_class, event, name, result, result_value, year, indoor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source, r.age_class, r.event, r.name, r.result, result_val, r.year, int(r.indoor)),
        )
        count += cursor.rowcount
    conn.commit()
    return count


def get_records(conn: sqlite3.Connection, source: str) -> list[ClubRecord]:
    """Get all records for a given source."""
    cursor = conn.execute(
        "SELECT age_class, event, name, result, year, indoor FROM records WHERE source = ?",
        (source,),
    )
    return [
        ClubRecord(age_class=row[0], event=row[1], name=row[2], result=row[3], year=row[4], indoor=bool(row[5]))
        for row in cursor.fetchall()
    ]


def get_best_per_event(conn: sqlite3.Connection, source: str) -> dict[tuple[str, str], ClubRecord]:
    """Get the best record per (age_class, event) for a source.

    Returns a dict keyed by (age_class, event), ignoring indoor/outdoor distinction.
    """
    records = get_records(conn, source)

    from main import classify_event, pick_best_record

    grouped: dict[tuple[str, str], list[ClubRecord]] = {}
    for r in records:
        key = (r.age_class, r.event)
        grouped.setdefault(key, []).append(r)

    best: dict[tuple[str, str], ClubRecord] = {}
    for key, group in grouped.items():
        try:
            cat = classify_event(key[1])
            best[key] = pick_best_record(group, cat)
        except ValueError:
            pass
    return best
