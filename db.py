
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any


def init_db(database_url: str = "") -> dict[str, Any]:
    url = database_url or os.getenv("DATABASE_URL", "")
    if url:
        try:
            import psycopg2
            conn = psycopg2.connect(url)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_name TEXT,
                    engine_name TEXT,
                    plan_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS app_visits (
                    id INTEGER PRIMARY KEY,
                    visit_count INTEGER NOT NULL
                );
                INSERT INTO app_visits (id, visit_count)
                VALUES (1, 0)
                ON CONFLICT (id) DO NOTHING;
            """)
            cur.close()
            conn.close()
            return {"kind": "postgres", "url": url}
        except Exception:
            # Safe fallback to SQLite.
            pass

    db_path = os.getenv("SOW_PLANNER_SQLITE_PATH", os.path.join("data", "planner.sqlite3"))
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source_name TEXT,
            engine_name TEXT,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_visits (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            visit_count INTEGER NOT NULL
        )
    """)
    conn.execute("INSERT OR IGNORE INTO app_visits (id, visit_count) VALUES (1, 0)")
    conn.commit()
    conn.close()
    return {"kind": "sqlite", "path": db_path}


@contextmanager
def _sqlite(path: str):
    conn = sqlite3.connect(path, check_same_thread=False)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _sqlite_path(db: dict[str, Any]) -> str:
    return db["path"]


def create_project(db: dict[str, Any], name: str, source_name: str, plan: dict[str, Any], engine_name: str) -> int:
    if db["kind"] == "postgres":
        import psycopg2
        conn = psycopg2.connect(db["url"])
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO projects (name, source_name, engine_name, plan_json) VALUES (%s,%s,%s,%s) RETURNING id",
                (name, source_name, engine_name, json.dumps(plan)),
            )
            pid = cur.fetchone()[0]
            conn.commit()
            return int(pid)
        finally:
            conn.close()

    with _sqlite(_sqlite_path(db)) as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, source_name, engine_name, plan_json, created_at) VALUES (?,?,?,?,?)",
            (name, source_name, engine_name, json.dumps(plan), datetime.now(timezone.utc).isoformat()),
        )
        return int(cur.lastrowid)


def list_projects(db: dict[str, Any]) -> list[dict[str, Any]]:
    if db["kind"] == "postgres":
        import psycopg2
        conn = psycopg2.connect(db["url"])
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, source_name, created_at FROM projects ORDER BY created_at DESC")
            rows = cur.fetchall()
        finally:
            conn.close()
        return [{"id": r[0], "label": f"{r[1]} — {r[2] or 'SOW'}", "name": r[1], "source_name": r[2], "created_at": str(r[3])} for r in rows]

    with _sqlite(_sqlite_path(db)) as conn:
        rows = conn.execute("SELECT id, name, source_name, created_at FROM projects ORDER BY id DESC").fetchall()
    return [{"id": r[0], "label": f"{r[1]} — {r[2] or 'SOW'}", "name": r[1], "source_name": r[2], "created_at": r[3]} for r in rows]


def load_project(db: dict[str, Any], project_id: int) -> dict[str, Any] | None:
    if db["kind"] == "postgres":
        import psycopg2
        conn = psycopg2.connect(db["url"])
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, source_name, engine_name, plan_json, created_at FROM projects WHERE id=%s", (project_id,))
            row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "source_name": row[2], "engine_name": row[3], "plan": json.loads(row[4]), "created_at": str(row[5])}

    with _sqlite(_sqlite_path(db)) as conn:
        row = conn.execute("SELECT id, name, source_name, engine_name, plan_json, created_at FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "source_name": row[2], "engine_name": row[3], "plan": json.loads(row[4]), "created_at": row[5]}


def record_visit(db: dict[str, Any]) -> int:
    if db["kind"] == "postgres":
        import psycopg2
        conn = psycopg2.connect(db["url"])
        try:
            cur = conn.cursor()
            cur.execute("UPDATE app_visits SET visit_count = visit_count + 1 WHERE id=1 RETURNING visit_count")
            count = cur.fetchone()[0]
            conn.commit()
            return int(count)
        finally:
            conn.close()

    with _sqlite(_sqlite_path(db)) as conn:
        conn.execute("UPDATE app_visits SET visit_count = visit_count + 1 WHERE id=1")
        row = conn.execute("SELECT visit_count FROM app_visits WHERE id=1").fetchone()
        return int(row[0])


def get_project_count(db: dict[str, Any]) -> int:
    if db["kind"] == "postgres":
        import psycopg2
        conn = psycopg2.connect(db["url"])
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM projects")
            return int(cur.fetchone()[0])
        finally:
            conn.close()
    with _sqlite(_sqlite_path(db)) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
