import json
import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/incidents.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS incidents ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "alert TEXT, category TEXT, explanation TEXT, "
            "explained_by TEXT, result_json TEXT)"
        )

def save_incident(alert: str, result: dict):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO incidents (alert, category, explanation, explained_by, result_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (alert, result["category"], result["explanation"],
             result["explained_by"], json.dumps(result)),
        )

def top_causes() -> list:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT category, COUNT(*) FROM incidents "
            "GROUP BY category ORDER BY COUNT(*) DESC"
        ).fetchall()
    return [{"category": category, "count": count} for category, count in rows]

def recent_incidents(limit: int = 10) -> list:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, created_at, alert, category, explained_by "
            "FROM incidents ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    keys = ["id", "created_at", "alert", "category", "explained_by"]
    return [dict(zip(keys, row)) for row in rows]