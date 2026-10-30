import logging
from pathlib import Path
from urllib.parse import quote

from a2wsgi import WSGIMiddleware
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from app import ai, database
from flask_app import flask_app

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "frontend" / "dist"  # the React app, after "npm run build"
logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/flask", WSGIMiddleware(flask_app))  # adding, importing and exporting notes
api = APIRouter(prefix="/api")

database.init_db()


def get_note_or_404(note_id):
    note = database.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


def get_chat_or_404(chat_id):
    chat = database.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


# ---------- Notes ----------

class NoteIn(BaseModel):
    title: str
    body: str = ""
    tags: str | list[str] = ""  # "python, ideas", or a list as older clients send it
    kind: str = "note"
    steps: str = ""  # plans: one step per line
    deadline: str = ""  # plans: YYYY-MM-DD


@api.get("/notes")
def list_notes(tag: str | None = None):
    return database.get_notes(tag)


@api.get("/notes/search")
def search(q: str):
    return database.search_notes(q)


@api.get("/notes/{note_id}")
def read_note(note_id: int):
    return get_note_or_404(note_id)


@api.put("/notes/{note_id}")
def edit_note(note_id: int, note: NoteIn):
    old = get_note_or_404(note_id)
    title, body = note.title.strip(), note.body.strip()
    problem = database.check_note(note.kind, title, body)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    # steps that were ticked stay ticked after an edit
    extra = database.make_extra(note.kind, note.steps, note.deadline, old["extra"].get("steps"))
    database.update_note(note_id, title, body, note.tags, note.kind, extra)
    return database.get_note(note_id)


@api.delete("/notes/{note_id}")
def remove_note(note_id: int):
    if not database.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Deleted"}


class PinIn(BaseModel):
    pinned: bool


@api.put("/notes/{note_id}/pinned")
def pin_note(note_id: int, pin: PinIn):
    get_note_or_404(note_id)
    database.set_pinned(note_id, pin.pinned)
    return database.get_note(note_id)


class StepIn(BaseModel):
    done: bool


@api.put("/notes/{note_id}/steps/{index}")
def tick_step(note_id: int, index: int, step: StepIn):
    get_note_or_404(note_id)
    database.set_step_done(note_id, index, step.done)
    return database.get_note(note_id)


@api.get("/notes/{note_id}/related")
def related(note_id: int):
    return ai.related_notes(note_id)


@api.get("/tags")
def tags():
    return database.get_all_tags()


@api.get("/stats")
def stats():
    return database.get_stats()


@api.get("/graph")
def graph():
    """How notes connect, for the knowledge graph on the Dashboard."""
    return [{"from": a, "to": b, "how": how} for a, b, how in ai.connections()]


# ---------- Chats ----------

ERROR_TEXT = "I couldn't reach the AI model. Is Ollama running, and did you download the model?"


@api.get("/chats")
def list_chats():
    return database.get_chats()


@api.post("/chats")
def new_chat():
    # reuse an empty chat instead of piling up blank ones
    empty = database.get_empty_chat()
    return {"id": empty if empty is not None else database.create_chat()}


@api.post("/chats/about/{note_id}")
def ask_about_note(note_id: int):
    """Start a chat about one note (the "Ask about this note" button in the Dashboard)."""
    note = get_note_or_404(note_id)
    return {"id": database.create_chat(f"About: {note['title']}"[:60], note_id)}


@api.get("/chats/{chat_id}")
def read_chat(chat_id: int):
    chat = get_chat_or_404(chat_id)
    focus = database.get_note(chat["note_id"]) if chat["note_id"] else None
    return {"chat": chat, "messages": database.get_messages(chat_id), "focus": focus}


@api.delete("/chats/{chat_id}")
def delete_chat(chat_id: int):
    database.delete_chat(chat_id)
    return {"message": "Deleted"}


class QuestionIn(BaseModel):
    question: str


@api.post("/chats/{chat_id}/ask")
def ask(chat_id: int, body: QuestionIn):
    chat = get_chat_or_404(chat_id)
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Ask a question first")

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
        # headers must be plain ASCII, so the title is URL-encoded
        "X-Chat-Title": quote(chat["title"]),
        # tells the page to ask for an AI-written title once the answer is done
        "X-Needs-Title": "1" if needs_title(chat) else "0",
    })


def needs_title(chat):
    # chats about a note keep their "About: ..." name
    return not chat["auto_titled"] and chat["note_id"] is None


@api.post("/chats/{chat_id}/title")
def make_chat_title(chat_id: int):
    """Let the AI name the chat from its first question and answer."""
    chat = get_chat_or_404(chat_id)
    if not needs_title(chat):
        return {"title": chat["title"]}

    messages = database.get_messages(chat_id)
    question = next((m for m in messages if m["role"] == "user"), None)
    answer = next((m for m in messages if m["role"] == "assistant" and not m["error"]), None)
    if question is None or answer is None:
        return {"title": chat["title"]}

    try:
        title = ai.make_title(question["content"], answer["content"])
    except ai.AI_ERRORS:
        logger.exception("Could not make a chat title")
        return {"title": chat["title"]}  # keep the shortened question for now, try again next answer
    if title:
        database.rename_chat(chat_id, title, auto_titled=True)
        chat["title"] = title
    return {"title": chat["title"]}


app.include_router(api)


# ---------- Old addresses, from before the React app ----------

@app.get("/fastapi", include_in_schema=False)
def old_ask_page(chat: int | None = None):
    return RedirectResponse(f"/ask/{chat}" if chat else "/ask")


@app.get("/ask/note/{note_id}", include_in_schema=False)
def old_ask_about_note(note_id: int):
    return RedirectResponse(f"/ask/{ask_about_note(note_id)['id']}")


class OldNoteIn(BaseModel):
    title: str
    body: str
    tags: list[str] = []
    kind: str = "note"
    extra: dict = {}  # plan: {"steps": [{"text", "done"}], "deadline"}


@app.post("/notes", tags=["old API"])
def old_create_note(note: OldNoteIn):
    title, body = note.title.strip(), note.body.strip()
    problem = database.check_note(note.kind, title, body)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    note_id = database.add_note(title, body, note.tags, note.kind, note.extra)
    return {"id": note_id, "message": "Note saved"}


@app.put("/notes/{note_id}", tags=["old API"])
def old_edit_note(note_id: int, note: OldNoteIn):
    if not database.update_note(note_id, note.title, note.body, note.tags, note.kind, note.extra):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Updated"}


# the rest of the old note API answers the same as the new one
app.get("/notes", tags=["old API"])(list_notes)
app.get("/notes/search", tags=["old API"])(search)
app.get("/notes/{note_id}/related", tags=["old API"])(related)
app.delete("/notes/{note_id}", tags=["old API"])(remove_note)


# ---------- The React app ----------

@app.get("/{path:path}", include_in_schema=False)
def react_app(path: str):
    """Every other page is handled by React, which picks what to show from the URL."""
    file = (DIST_DIR / path).resolve()
    if path and file.is_file() and file.is_relative_to(DIST_DIR.resolve()):
        return FileResponse(file)  # the built JavaScript and CSS in assets/, favicon.svg, ...
    if path.startswith(("api/", "assets/")):
        # a missing file or API route; sending the React page back would only confuse the browser
        raise HTTPException(status_code=404, detail="Not found")
    if not (DIST_DIR / "index.html").is_file():
        return PlainTextResponse(
            "The React app isn't built yet. Run \"npm run build\" in frontend/, "
            "or use \"python run.py\" and open http://localhost:5173",
            status_code=503,
        )
    return FileResponse(DIST_DIR / "index.html")
