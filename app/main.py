from pathlib import Path

from a2wsgi import WSGIMiddleware
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import ai, database
from flask_app import flask_app

BASE_DIR = Path(__file__).resolve().parent.parent

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
def ask_page(request: Request):
    return templates.TemplateResponse(request, "ask.html", {})


@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {})


# ---------- The AI route used by the Ask page ----------

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


# ---------- JSON API (still available at /docs) ----------

class NoteIn(BaseModel):
    title: str
    body: str


@app.post("/notes")
def create_note(note: NoteIn):
    note_id = database.add_note(note.title, note.body)
    return {"id": note_id, "message": "Note saved"}


@app.get("/notes")
def list_notes():
    return database.get_notes()


@app.get("/notes/search")
def search(q: str):
    return database.search_notes(q)


@app.delete("/notes/{note_id}")
def remove_note(note_id: int):
    if not database.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Deleted"}