from flask import Flask, Response, redirect, render_template, request, url_for

from app import database, importer
from app.static_files import static_url

flask_app = Flask(__name__, template_folder="templates")
flask_app.jinja_env.globals["static_url"] = static_url
flask_app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # imports up to 25 MB
database.init_db()


@flask_app.route("/")
def home():
    kind = request.args.get("kind", "note")
    return render_template(
        "capture.html",
        kinds=database.KINDS,
        kind=kind if kind in database.KINDS else "note",
        languages=database.LANGUAGES,
        saved=request.args.get("saved"),
        imported=request.args.get("imported"),
        problems=request.args.getlist("problem"),
    )


@flask_app.route("/add", methods=["POST"])
def add():
    form = request.form
    kind = form.get("kind", "note")
    title = form.get("title", "").strip()
    body = form.get("body", "").strip()

    # ideas and plans can be saved without a body, notes and code can't
    if not title or (kind in ("note", "code") and not body):
        return redirect(url_for("home", kind=kind, problem="Please fill in the title and the text."))

    extra = database.make_extra(kind, form.get("steps", ""), form.get("deadline", ""), form.get("language", ""))
    database.add_note(title, body, form.get("tags", ""), kind, extra)
    # stay on the same type, so saving several ideas in a row is quick
    return redirect(url_for("home", kind=kind, saved=1))


@flask_app.route("/import", methods=["POST"])
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
    return redirect(url_for("home", imported=count, problem=problems))


@flask_app.route("/export")
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
