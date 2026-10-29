import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "notes.db"

# The kinds of note you can save, and how they are shown
KINDS = {"note": "📝 Note", "idea": "💡 Idea", "plan": "🗺️ Plan", "code": "💻 Code"}


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)  # creates data/ if missing
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read rows like dictionaries
    return conn


def _add_column(conn, table, column, definition):
    """Older databases were made before some columns existed, so add them if missing."""
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        return True
    return False


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
        _add_column(conn, "notes", "tags", "TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "notes", "kind", "TEXT NOT NULL DEFAULT 'note'")
        _add_column(conn, "notes", "pinned", "INTEGER NOT NULL DEFAULT 0")
        _add_column(conn, "notes", "embedding", "TEXT")  # filled in by the AI when needed

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'New chat',
                note_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT NOT NULL DEFAULT '[]',
                error INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Messages saved before there were several chats go into one "Earlier chat"
        if _add_column(conn, "messages", "chat_id", "INTEGER"):
            if conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]:
                chat_id = conn.execute("INSERT INTO chats (title) VALUES ('Earlier chat')").lastrowid
                conn.execute("UPDATE messages SET chat_id = ?", (chat_id,))


# ---------- Tags ----------

def clean_tags(text):
    """Turn "Python, ideas , python" into "python,ideas"."""
    tags = []
    for tag in (text or "").split(","):
        tag = tag.strip().lower()
        if tag and tag not in tags:
            tags.append(tag)
    return ",".join(tags)


def _note(row):
    note = dict(row)
    note["tags"] = note["tags"].split(",") if note["tags"] else []
    note["pinned"] = bool(note["pinned"])
    note.pop("embedding", None)  # big list of numbers, only the AI needs it
    return note


def _kind(kind):
    return kind if kind in KINDS else "note"


def get_all_tags():
    tags = set()
    for note in get_notes():
        tags.update(note["tags"])
    return sorted(tags)


# ---------- Notes ----------

def add_note(title, body, tags="", kind="note"):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO notes (title, body, tags, kind) VALUES (?, ?, ?, ?)",
            (title, body, clean_tags(tags), _kind(kind)),
        )
        return cursor.lastrowid


def get_notes(tag=None):
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM notes ORDER BY pinned DESC, id DESC").fetchall()
    notes = [_note(row) for row in rows]
    if tag:
        notes = [n for n in notes if tag in n["tags"]]
    return notes


def search_notes(query):
    with get_connection() as conn:
        like = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM notes WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? "
            "ORDER BY pinned DESC, id DESC",
            (like, like, like),
        ).fetchall()
        return [_note(row) for row in rows]


def delete_note(note_id):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return cursor.rowcount > 0


def get_note(note_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return _note(row) if row else None


def update_note(note_id, title, body, tags="", kind="note"):
    with get_connection() as conn:
        # the text changed, so the AI has to work out its meaning again
        cursor = conn.execute(
            "UPDATE notes SET title = ?, body = ?, tags = ?, kind = ?, embedding = NULL WHERE id = ?",
            (title, body, clean_tags(tags), _kind(kind), note_id),
        )
        return cursor.rowcount > 0


def set_pinned(note_id, pinned):
    with get_connection() as conn:
        conn.execute("UPDATE notes SET pinned = ? WHERE id = ?", (int(pinned), note_id))


# ---------- Embeddings (used by the AI to find notes with similar meaning) ----------

def get_embeddings():
    """Return {note_id: vector} for every note that has one."""
    with get_connection() as conn:
        rows = conn.execute("SELECT id, embedding FROM notes WHERE embedding IS NOT NULL").fetchall()
    return {row["id"]: json.loads(row["embedding"]) for row in rows}


def get_notes_without_embedding():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM notes WHERE embedding IS NULL").fetchall()
    return [_note(row) for row in rows]


def set_embedding(note_id, vector):
    with get_connection() as conn:
        conn.execute("UPDATE notes SET embedding = ? WHERE id = ?", (json.dumps(vector), note_id))


# ---------- Chats ----------

def create_chat(title="New chat", note_id=None):
    with get_connection() as conn:
        return conn.execute(
            "INSERT INTO chats (title, note_id) VALUES (?, ?)", (title, note_id)
        ).lastrowid


def get_chats():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM chats ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]


def get_chat(chat_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        return dict(row) if row else None


def rename_chat(chat_id, title):
    with get_connection() as conn:
        conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))


def delete_chat(chat_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))


# ---------- Chat messages ----------

def add_message(chat_id, role, content, sources=None, error=False):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (chat_id, role, content, sources, error) VALUES (?, ?, ?, ?, ?)",
            (chat_id, role, content, json.dumps(sources or []), int(error)),
        )


def get_messages(chat_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,)
        ).fetchall()
    messages = []
    for row in rows:
        m = dict(row)
        m["sources"] = json.loads(m["sources"])
        m["error"] = bool(m["error"])
        messages.append(m)
    return messages


# ---------- Numbers for the Command Center ----------

def get_stats():
    with get_connection() as conn:
        def count(sql):
            return conn.execute(sql).fetchone()[0]

        return {
            "notes": count("SELECT COUNT(*) FROM notes"),
            "this_week": count("SELECT COUNT(*) FROM notes WHERE created_at >= datetime('now', '-7 days')"),
            "pinned": count("SELECT COUNT(*) FROM notes WHERE pinned = 1"),
            "chats": count("SELECT COUNT(*) FROM chats"),
            "questions": count("SELECT COUNT(*) FROM messages WHERE role = 'user'"),
        }
