import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "notes.db"


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)  # creates data/ if missing
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read rows like dictionaries
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def add_note(title, body):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO notes (title, body) VALUES (?, ?)", (title, body)
        )
        return cursor.lastrowid


def get_notes():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]


def search_notes(query):
    with get_connection() as conn:
        like = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM notes WHERE title LIKE ? OR body LIKE ? ORDER BY id DESC",
            (like, like),
        ).fetchall()
        return [dict(row) for row in rows]


def delete_note(note_id):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return cursor.rowcount > 0