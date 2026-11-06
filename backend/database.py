"""SQLite：启动时建表，所有语句都用参数占位符。"""

import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "data"


def data_dir():
    return Path(os.environ.get("SHEETWISE_DATA", DEFAULT_DATA))


def db_path():
    return Path(os.environ.get("SHEETWISE_DB", data_dir() / "sheetwise.db"))


def connect():
    data_dir().mkdir(parents=True, exist_ok=True)
    (data_dir() / "uploads").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              session_id TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS datasets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              file_name TEXT NOT NULL,
              file_size INTEGER NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              col_count INTEGER NOT NULL,
              truncated INTEGER NOT NULL DEFAULT 0,
              question TEXT NOT NULL DEFAULT '',
              plan_json TEXT NOT NULL DEFAULT '{}',
              answer_json TEXT NOT NULL DEFAULT '{}',
              stats_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS anomalies (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
              issue_key TEXT NOT NULL,
              type TEXT NOT NULL,
              row_index INTEGER NOT NULL,
              col_index INTEGER NOT NULL,
              field TEXT NOT NULL,
              original TEXT NOT NULL,
              suggestion_json TEXT NOT NULL,
              learned INTEGER NOT NULL DEFAULT 0,
              decision TEXT,
              edited_value TEXT,
              UNIQUE(dataset_id, issue_key)
            );
            CREATE TABLE IF NOT EXISTS reports (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              dataset_id INTEGER NOT NULL UNIQUE REFERENCES datasets(id) ON DELETE CASCADE,
              created_at TEXT NOT NULL,
              issues_found INTEGER NOT NULL,
              fixed INTEGER NOT NULL,
              ignored INTEGER NOT NULL,
              duplicates_removed INTEGER NOT NULL,
              quality_score REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS learned_rules (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              rule_key TEXT NOT NULL,
              suggestion_json TEXT NOT NULL,
              UNIQUE(user_id, rule_key)
            );
            CREATE TABLE IF NOT EXISTS usage_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              kind TEXT NOT NULL,
              prompt_tokens INTEGER NOT NULL DEFAULT 0,
              completion_tokens INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ai_asks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
              question TEXT NOT NULL,
              answer TEXT NOT NULL,
              source TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS templates (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              slug TEXT UNIQUE,
              name TEXT NOT NULL,
              summary TEXT NOT NULL,
              note TEXT NOT NULL,
              headers_json TEXT NOT NULL,
              sample_json TEXT NOT NULL,
              rules_json TEXT NOT NULL,
              dirty_csv TEXT NOT NULL,
              builtin INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        _ensure_column(conn, "datasets", "template_name", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "datasets", "rules_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "datasets", "log_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "anomalies", "auto_fixed", "INTEGER NOT NULL DEFAULT 0")
        _seed_templates(conn)


def _ensure_column(conn, table, column, ddl):
    names = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _seed_templates(conn):
    from templates_data import TEMPLATES
    for item in TEMPLATES:
        exists = conn.execute("SELECT id FROM templates WHERE slug = ?", (item["slug"],)).fetchone()
        payload = (
            item["name"], item["summary"], item["note"],
            dumps(item["headers"]), dumps(item["sample"]), dumps(item["rules"]), item["dirty"],
            item["slug"],
        )
        if exists:
            conn.execute(
                """
                UPDATE templates
                SET name = ?, summary = ?, note = ?, headers_json = ?, sample_json = ?, rules_json = ?, dirty_csv = ?
                WHERE slug = ?
                """,
                payload,
            )
        else:
            conn.execute(
                """
                INSERT INTO templates (slug, name, summary, note, headers_json, sample_json, rules_json, dirty_csv, builtin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (item["slug"], item["name"], item["summary"], item["note"], dumps(item["headers"]), dumps(item["sample"]), dumps(item["rules"]), item["dirty"]),
            )


def dumps(value):
    return json.dumps(value, ensure_ascii=False)


def loads(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
