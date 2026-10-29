"""Turn uploaded .txt, .md and .pdf files into notes."""
import io
import re
from pathlib import Path

from pypdf import PdfReader

SUPPORTED = {".txt", ".md", ".pdf"}
MAX_NOTE_LENGTH = 4000  # longer text is split into parts so the AI can read each one


def notes_from_file(filename, data):
    """Return a list of {"title", "body", "tags", "kind"} for one file."""
    path = Path(filename)
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"{filename}: only .txt, .md and .pdf files can be imported")

    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        sections = [(path.stem, text, "", "note")]
    else:
        text = data.decode("utf-8", errors="replace")
        sections = _markdown_sections(text, path.stem) if ext == ".md" else [(path.stem, text, "", "note")]

    notes = []
    for title, body, tags, kind in sections:
        parts = _split(body.strip())
        for i, part in enumerate(parts, start=1):
            part_title = f"{title} (part {i})" if len(parts) > 1 else title
            notes.append({"title": part_title, "body": part, "tags": tags + ",imported", "kind": kind})
    if not notes:
        raise ValueError(f"{filename}: no text found (scanned PDFs can't be read)")
    return notes


def _markdown_sections(text, fallback_title):
    """Split on "# Heading" lines. Also reads the app's own export (Type:/Tags: lines, --- separators)."""
    sections = []
    title, lines = fallback_title, []

    def finish():
        body_lines = [l for l in lines if l.strip() != "---"]
        tags, kind = "", "note"
        # "Type: code" and "Tags: a, b" right under the heading
        while True:
            first = next((i for i, l in enumerate(body_lines) if l.strip()), None)
            if first is not None and body_lines[first].startswith("Type: "):
                kind = body_lines.pop(first)[len("Type: "):].strip()
            elif first is not None and body_lines[first].startswith("Tags: "):
                tags = body_lines.pop(first)[len("Tags: "):]
            else:
                break
        # the "*2026-10-28 08:55:04*" date line the export adds at the end
        last = next((i for i in reversed(range(len(body_lines))) if body_lines[i].strip()), None)
        if last is not None and re.fullmatch(r"\*\d{4}-\d\d-\d\d[^*]*\*", body_lines[last].strip()):
            body_lines.pop(last)
        body = "\n".join(body_lines).strip()
        if body:
            sections.append((title, body, tags, kind))

    for line in text.splitlines():
        if line.startswith("# "):
            finish()
            title, lines = line[2:].strip(), []
        else:
            lines.append(line)
    finish()
    return sections


def _split(text):
    """Split long text into parts of about MAX_NOTE_LENGTH, at paragraph breaks."""
    if not text:
        return []
    parts, current = [], ""
    for paragraph in re.split(r"\n\s*\n", text):
        while len(paragraph) > MAX_NOTE_LENGTH:  # a single huge paragraph
            if current:
                parts.append(current)
                current = ""
            parts.append(paragraph[:MAX_NOTE_LENGTH])
            paragraph = paragraph[MAX_NOTE_LENGTH:]
        if current and len(current) + len(paragraph) + 2 > MAX_NOTE_LENGTH:
            parts.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current.strip():
        parts.append(current)
    return parts
