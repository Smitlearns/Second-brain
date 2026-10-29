import json
import logging
from pathlib import Path
from urllib.parse import quote

from a2wsgi import WSGIMiddleware
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import ai, database
from flask_app import flask_app

BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/flask", WSGIMiddleware(flask_app))
templates = Jinja2Templates(directory=BASE_DIR / "templates")

database.init_db()


# ---------- Pages ----------

@app.get("/")
def root():
    return RedirectResponse("/flask/")  # the Notes page (Flask) comes first


@app.get("/fastapi")
def ask_page(request: Request, chat: int | None = None):
    chats = database.get_chats()
    if chat is None:
        if not chats:
            return RedirectResponse(f"/fastapi?chat={database.create_chat()}")
        return RedirectResponse(f"/fastapi?chat={chats[0]['id']}")

    current = database.get_chat(chat)
    if current is None:
        return RedirectResponse("/fastapi")
    focus = database.get_note(current["note_id"]) if current["note_id"] else None
    return templates.TemplateResponse(request, "ask.html", {
        "chats": chats,
        "chat": current,
        "history": database.get_messages(chat),
        "focus": focus,
    })


@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {})


# ---------- Chat routes used by the Ask page ----------

ERROR_TEXT = "I couldn't reach the AI model. Is Ollama running, and did you download the model?"


@app.post("/chats")
def new_chat():
    # reuse an empty chat instead of piling up blank ones
    for c in database.get_chats():
        if c["note_id"] is None and not database.get_messages(c["id"]):
            return RedirectResponse(f"/fastapi?chat={c['id']}", status_code=303)
    return RedirectResponse(f"/fastapi?chat={database.create_chat()}", status_code=303)


@app.post("/chats/{chat_id}/delete")
def delete_chat(chat_id: int):
    database.delete_chat(chat_id)
    return RedirectResponse("/fastapi", status_code=303)


@app.get("/ask/note/{note_id}")
def ask_about_note(note_id: int):
    """Start a chat about one note (the "Ask about this note" button in the Dashboard)."""
    note = database.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    chat_id = database.create_chat(f"About: {note['title']}"[:60], note_id)
    return RedirectResponse(f"/fastapi?chat={chat_id}")


@app.post("/chats/{chat_id}/ask")
def ask(chat_id: int, question: str = Form(...)):
    chat = database.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    # error messages are shown in the chat but never sent to the AI
    # only the last 4 messages go to the AI, to keep answers quick
    history = [m for m in database.get_messages(chat_id) if not m["error"]][-4:]
    database.add_message(chat_id, "user", question)
    if chat["title"] == "New chat":
        chat["title"] = question[:40] + ("..." if len(question) > 40 else "")
        database.rename_chat(chat_id, chat["title"])

    focus = database.get_note(chat["note_id"]) if chat["note_id"] else None
    messages, sources = ai.prepare(question, history, focus)

    def generate():
        answer, error = "", False
        try:
            for piece in ai.stream_answer(messages):
                answer += piece
                yield piece
        except ai.AI_ERRORS:
            logger.exception("Could not reach the AI model")
            error = True
            text = ("\n\n" if answer else "") + ERROR_TEXT
            answer += text
            yield text
        finally:
            # runs even if you leave the page halfway, so the chat keeps what was said
            database.add_message(chat_id, "assistant", answer, [] if error else sources, error)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8", headers={
        # headers must be plain ASCII, so the note titles are URL-encoded
        "X-Sources": quote(json.dumps(sources)),
        "X-Chat-Title": quote(chat["title"]),
    })


# ---------- JSON API (still available at /docs) ----------

class NoteIn(BaseModel):
    title: str
    body: str
    tags: list[str] = []
    kind: str = "note"


@app.post("/notes")
def create_note(note: NoteIn):
    note_id = database.add_note(note.title, note.body, ",".join(note.tags), note.kind)
    return {"id": note_id, "message": "Note saved"}


@app.get("/notes")
def list_notes(tag: str | None = None):
    return database.get_notes(tag)


@app.put("/notes/{note_id}")
def edit_note(note_id: int, note: NoteIn):
    if not database.update_note(note_id, note.title, note.body, ",".join(note.tags), note.kind):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Updated"}


@app.get("/notes/search")
def search(q: str):
    return database.search_notes(q)


@app.get("/notes/{note_id}/related")
def related(note_id: int):
    return ai.related_notes(note_id)


@app.delete("/notes/{note_id}")
def remove_note(note_id: int):
    if not database.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Deleted"}