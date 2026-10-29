import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "notes.db"

# The kinds of note you can save, and how they are shown
KINDS = {"note": "📝 Note", "idea": "💡 Idea", "plan": "🗺️ Plan", "code": "💻 Code"}
LANGUAGES = ["python", "javascript", "typescript", "html", "css", "sql", "bash", "java", "c", "cpp", "other"]


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
        # fields only some types have: plan steps and deadline, code language
        _add_column(conn, "notes", "extra", "TEXT NOT NULL DEFAULT '{}'")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'New chat',
                note_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _add_column(conn, "chats", "auto_titled", "INTEGER NOT NULL DEFAULT 0")  # 1 once the AI named it
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
    note["extra"] = json.loads(note["extra"])
    note.pop("embedding", None)  # big list of numbers, only the AI needs it
    return note


def _kind(kind):
    return kind if kind in KINDS else "note"


def make_extra(kind, steps="", deadline="", language="", old_steps=None):
    """Build the type-specific fields from a form. Steps that were ticked stay ticked after an edit."""
    if kind == "plan":
        done = {s["text"] for s in old_steps or [] if s["done"]}
        lines = [line.strip().lstrip("-*").strip() for line in steps.splitlines()]
        return {"steps": [{"text": l, "done": l in done} for l in lines if l], "deadline": deadline or ""}
    if kind == "code":
        return {"language": language if language in LANGUAGES else "other"}
    return {}


def full_text(note):
    """Everything worth searching in a note, including plan steps and code language."""
    extra = note["extra"]
    parts = [note["body"]]
    if extra.get("steps"):
        parts.append("Steps: " + "; ".join(s["text"] for s in extra["steps"]))
    if extra.get("deadline"):
        parts.append("Deadline: " + extra["deadline"])
    if extra.get("language"):
        parts.append("Language: " + extra["language"])
    return "\n".join(p for p in parts if p)


def get_all_tags():
    tags = set()
    for note in get_notes():
        tags.update(note["tags"])
    return sorted(tags)


# ---------- Notes ----------

def add_note(title, body, tags="", kind="note", extra=None):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO notes (title, body, tags, kind, extra) VALUES (?, ?, ?, ?, ?)",
            (title, body, clean_tags(tags), _kind(kind), json.dumps(extra or {})),
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
            "SELECT * FROM notes WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? OR extra LIKE ? "
            "ORDER BY pinned DESC, id DESC",
            (like, like, like, like),
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


def update_note(note_id, title, body, tags="", kind="note", extra=None):
    with get_connection() as conn:
        # the text changed, so the AI has to work out its meaning again
        cursor = conn.execute(
            "UPDATE notes SET title = ?, body = ?, tags = ?, kind = ?, extra = ?, embedding = NULL "
            "WHERE id = ?",
            (title, body, clean_tags(tags), _kind(kind), json.dumps(extra or {}), note_id),
        )
        return cursor.rowcount > 0


def set_step_done(note_id, index, done):
    """Tick or untick one step of a plan."""
    note = get_note(note_id)
    steps = note["extra"].get("steps", []) if note else []
    if 0 <= index < len(steps):
        steps[index]["done"] = done
        with get_connection() as conn:
            conn.execute("UPDATE notes SET extra = ? WHERE id = ?", (json.dumps(note["extra"]), note_id))


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


def rename_chat(chat_id, title, auto_titled=False):
    with get_connection() as conn:
        conn.execute(
            "UPDATE chats SET title = ?, auto_titled = ? WHERE id = ?", (title, int(auto_titled), chat_id)
        )


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
