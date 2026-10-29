from flask import Flask, Response, redirect, render_template, request, url_for

from app import database, importer

flask_app = Flask(__name__, template_folder="templates")
flask_app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # imports up to 25 MB
database.init_db()


@flask_app.route("/")
def home():
    return render_template(
        "capture.html",
        kinds=database.KINDS,
        saved=request.args.get("saved"),
        imported=request.args.get("imported"),
        problems=request.args.getlist("problem"),
    )


@flask_app.route("/add", methods=["POST"])
def add():
    database.add_note(
        request.form["title"],
        request.form["body"],
        request.form.get("tags", ""),
        request.form.get("kind", "note"),
    )
    return redirect(url_for("home", saved=1))


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
            database.add_note(n["title"], n["body"], n["tags"], n["kind"])
        count += len(notes)
    return redirect(url_for("home", imported=count, problem=problems))


@flask_app.route("/export")
def export():
    parts = []
    for n in database.get_notes():
        kind = f"Type: {n['kind']}\n" if n["kind"] != "note" else ""
        tags = f"Tags: {', '.join(n['tags'])}\n" if n["tags"] else ""
        details = f"{kind}{tags}\n" if kind or tags else ""
        parts.append(f"# {n['title']}\n\n{details}{n['body']}\n\n*{n['created_at']}*\n")
    markdown = "\n---\n\n".join(parts)
    return Response(
        markdown,
        mimetype="text/markdown",
        headers={"Content-Disposition": "attachment; filename=second-brain-notes.md"},
    )
