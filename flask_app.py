from flask import Flask, Response, redirect, render_template, request, url_for

from app import database

flask_app = Flask(__name__, template_folder="templates")
database.init_db()


@flask_app.route("/")
def home():
    return render_template("capture.html", saved=request.args.get("saved"))


@flask_app.route("/add", methods=["POST"])
def add():
    database.add_note(request.form["title"], request.form["body"])
    return redirect(url_for("home", saved=1))


@flask_app.route("/export")
def export():
    parts = [
        f"# {n['title']}\n\n{n['body']}\n\n*{n['created_at']}*\n"
        for n in database.get_notes()
    ]
    markdown = "\n---\n\n".join(parts)
    return Response(
        markdown,
        mimetype="text/markdown",
        headers={"Content-Disposition": "attachment; filename=second-brain-notes.md"},
    )