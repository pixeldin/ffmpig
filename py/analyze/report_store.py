import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


VISIT_INTERVAL_SECONDS = 1800


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(db_path):
    path = Path(db_path)
    if path.parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn):
    try:
        yield
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def ensure_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS log_state (
          log_path TEXT PRIMARY KEY,
          offset INTEGER NOT NULL DEFAULT 0,
          file_size INTEGER NOT NULL DEFAULT 0,
          fingerprint TEXT,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS raw_log_event (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_key TEXT NOT NULL UNIQUE,
          file_key TEXT NOT NULL,
          access_time TEXT NOT NULL,
          access_ts INTEGER NOT NULL,
          status_code INTEGER,
          raw_path TEXT NOT NULL,
          raw_line TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_raw_log_event_file_key
          ON raw_log_event(file_key);

        CREATE INDEX IF NOT EXISTS idx_raw_log_event_access_ts
          ON raw_log_event(access_ts);

        CREATE TABLE IF NOT EXISTS file_visit (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          file_key TEXT NOT NULL,
          access_time TEXT NOT NULL,
          access_ts INTEGER NOT NULL,
          raw_event_key TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL,
          FOREIGN KEY(raw_event_key) REFERENCES raw_log_event(event_key)
        );

        CREATE INDEX IF NOT EXISTS idx_file_visit_file_key
          ON file_visit(file_key);

        CREATE INDEX IF NOT EXISTS idx_file_visit_access_ts
          ON file_visit(access_ts);
        """
    )


def get_log_state(conn, log_path):
    row = conn.execute(
        """
        SELECT log_path, offset, file_size, fingerprint, updated_at
        FROM log_state
        WHERE log_path = ?
        """,
        (str(log_path),),
    ).fetchone()
    return dict(row) if row else None


def save_log_state(conn, log_path, offset, file_size, fingerprint=None):
    conn.execute(
        """
        INSERT INTO log_state (log_path, offset, file_size, fingerprint, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(log_path) DO UPDATE SET
          offset = excluded.offset,
          file_size = excluded.file_size,
          fingerprint = excluded.fingerprint,
          updated_at = excluded.updated_at
        """,
        (str(log_path), int(offset), int(file_size), fingerprint, now_text()),
    )


def insert_raw_event(conn, event):
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO raw_log_event (
          event_key,
          file_key,
          access_time,
          access_ts,
          status_code,
          raw_path,
          raw_line,
          created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["event_key"],
            event["file_key"],
            event["access_time"],
            int(event["access_ts"]),
            event.get("status_code"),
            event["raw_path"],
            event["raw_line"],
            now_text(),
        ),
    )
    return cursor.rowcount == 1


def get_last_visit_ts(conn, file_key):
    row = conn.execute(
        """
        SELECT access_ts
        FROM file_visit
        WHERE file_key = ?
        ORDER BY access_ts DESC
        LIMIT 1
        """,
        (file_key,),
    ).fetchone()
    return int(row["access_ts"]) if row else None


def insert_file_visit(conn, event):
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO file_visit (
          file_key,
          access_time,
          access_ts,
          raw_event_key,
          created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            event["file_key"],
            event["access_time"],
            int(event["access_ts"]),
            event["event_key"],
            now_text(),
        ),
    )
    return cursor.rowcount == 1


def maybe_insert_file_visit(conn, event, interval_seconds=VISIT_INTERVAL_SECONDS):
    last_visit_ts = get_last_visit_ts(conn, event["file_key"])
    if last_visit_ts is not None and int(event["access_ts"]) - last_visit_ts <= interval_seconds:
        return False
    return insert_file_visit(conn, event)


def query_visit_summary(conn):
    rows = conn.execute(
        """
        SELECT
          file_key,
          COUNT(*) AS count,
          GROUP_CONCAT(access_time, ',') AS times
        FROM (
          SELECT file_key, access_time, access_ts
          FROM file_visit
          ORDER BY file_key, access_ts
        )
        GROUP BY file_key
        ORDER BY file_key
        """
    ).fetchall()
    return {
        row["file_key"]: {
            "count": int(row["count"]),
            "times": row["times"].split(",") if row["times"] else [],
        }
        for row in rows
    }


def count_rows(conn, table_name):
    if table_name not in {"log_state", "raw_log_event", "file_visit"}:
        raise ValueError(f"Unsupported table: {table_name}")
    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return int(row["count"])
