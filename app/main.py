from pathlib import Path

from a2wsgi import WSGIMiddleware
from flask_app import flask_app
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import ai, database

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/capture", WSGIMiddleware(flask_app))
templates = Jinja2Templates(directory=BASE_DIR / "templates")

database.init_db()


class NoteIn(BaseModel):
    title: str
    body: str


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"notes": database.get_notes()}
    )

@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {})


@app.get("/partials/notes")
def notes_partial(request: Request, q: str = ""):
    notes = database.search_notes(q) if q else database.get_notes()
    return templates.TemplateResponse(request, "notes_list.html", {"notes": notes})


@app.post("/add")
def add_from_form(request: Request, title: str = Form(...), body: str = Form(...)):
    database.add_note(title, body)
    return templates.TemplateResponse(
        request, "notes_list.html", {"notes": database.get_notes()}
    )

@app.post("/ask")
def ask(request: Request, question: str = Form(...)):
    try:
        answer, sources = ai.ask_brain(question)
    except Exception:
        answer = "I couldn't reach the AI model. Is Ollama running, and did you download the model?"
        sources = []
    return templates.TemplateResponse(
        request, "answer.html", {"answer": answer, "sources": sources}
    )

@app.post("/delete/{note_id}")
def delete_from_form(note_id: int):
    database.delete_note(note_id)
    return HTMLResponse("")  # empty reply, so HTMX removes the note from the page