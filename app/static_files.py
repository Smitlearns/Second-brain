from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def static_url(name):
    """Link to a file in static/ with its last-changed time added, e.g. /static/style.css?v=1761725000.

    The link changes whenever the file changes, so browsers can't keep using an old cached copy.
    """
    version = int((STATIC_DIR / name).stat().st_mtime)
    return f"/static/{name}?v={version}"
