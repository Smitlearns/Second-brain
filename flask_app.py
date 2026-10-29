from flask import Flask, Response, jsonify, redirect, request

from app import database, importer

flask_app = Flask(__name__)
flask_app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # imports up to 25 MB
database.init_db()


@flask_app.get("/")
def old_notes_page():
    return redirect("/")  # the Notes page is part of the React app now


@flask_app.post("/notes")
def add():
    """Save a note from the Notes page. Plan steps come in as text, one per line."""
    form = request.get_json(silent=True)
    fields = ("kind", "title", "body", "tags", "steps", "deadline", "language")
    if not isinstance(form, dict) or not all(isinstance(form.get(f, ""), str) for f in fields):
        return jsonify(error="Send the note as a JSON object of text fields."), 400
    kind = form.get("kind", "note")
    title = form.get("title", "").strip()
    body = form.get("body", "").strip()

    problem = database.check_note(kind, title, body)
    if problem:
        return jsonify(error=problem), 400

    extra = database.make_extra(kind, form.get("steps", ""), form.get("deadline", ""), form.get("language", ""))
    note_id = database.add_note(title, body, form.get("tags", ""), kind, extra)
    return jsonify(id=note_id), 201


@flask_app.post("/import")
def import_files():
    count, problems = 0, []
    for file in request.files.getlist("files"):
        if not file.filename:
            continue
        try:
            notes = importer.notes_from_file(file.filename, file.read())
        except Exception as e:  # a broken PDF shouldn't stop the other files
            problems.append(str(e) if isinstance(e, ValueError) else f"{file.filename}: couldn't be read")
            continue
        for n in notes:
            database.add_note(n["title"], n["body"], n["tags"], n["kind"], n["extra"])
        count += len(notes)
    return jsonify(imported=count, problems=problems)


@flask_app.get("/export")
def export():
    parts = []
    for n in database.get_notes():
        extra = n["extra"]
        details = ""
        if n["kind"] != "note":
            details += f"Type: {n['kind']}\n"
        if n["tags"]:
            details += f"Tags: {', '.join(n['tags'])}\n"
        if extra.get("language"):
            details += f"Language: {extra['language']}\n"
        if extra.get("deadline"):
            details += f"Deadline: {extra['deadline']}\n"

        body = n["body"]
        if n["kind"] == "code":
            body = f"```{extra.get('language', '')}\n{body}\n```"
        if extra.get("steps"):
            steps = "\n".join(f"- [{'x' if s['done'] else ' '}] {s['text']}" for s in extra["steps"])
            body = f"{body}\n\n{steps}" if body else steps

        details = details + "\n" if details else ""
        parts.append(f"# {n['title']}\n\n{details}{body}\n\n*{n['created_at']}*\n")
    markdown = "\n---\n\n".join(parts)
    return Response(
        markdown,
        mimetype="text/markdown",
        headers={"Content-Disposition": "attachment; filename=second-brain-notes.md"},
    )
