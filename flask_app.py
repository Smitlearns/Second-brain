from flask import Flask, Response, redirect, render_template_string, request

from app import database

flask_app = Flask(__name__)
database.init_db()

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Quick Capture</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <main>
    <h1>Quick Capture</h1>
    <p class="empty">{{ count }} notes saved</p>

    <form action="/add" method="post" class="card">
      <input type="text" name="title" placeholder="Title" required>
      <textarea name="body" placeholder="Write your note..." rows="4" required></textarea>
      <button type="submit">Save note</button>
    </form>

    <a href="/export">Download all notes as Markdown</a>
  </main>
</body>
</html>
"""


@flask_app.route("/")
def home():
    return render_template_string(PAGE, count=len(database.get_notes()))


@flask_app.route("/add", methods=["POST"])
def add():
    database.add_note(request.form["title"], request.form["body"])
    return redirect("/")


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


if __name__ == "__main__":
    flask_app.run(port=5000, debug=True)