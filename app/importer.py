"""Turn uploaded .txt, .md and .pdf files into notes."""
import io
import re
from pathlib import Path

from pypdf import PdfReader

SUPPORTED = {".txt", ".md", ".pdf"}
MAX_NOTE_LENGTH = 4000  # longer text is split into parts so the AI can read each one


def notes_from_file(filename, data):
    """Return a list of {"title", "body", "tags", "kind", "extra"} for one file."""
    path = Path(filename)
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"{filename}: only .txt, .md and .pdf files can be imported")

    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        sections = [_section(path.stem, text)]
    else:
        text = data.decode("utf-8", errors="replace")
        sections = _markdown_sections(text, path.stem) if ext == ".md" else [_section(path.stem, text)]

    notes = []
    for section in sections:
        section["tags"] += ",imported"
        if section["kind"] != "note":  # plans and code stay in one piece
            notes.append(section)
            continue
        parts = _split(section["body"].strip())
        for i, part in enumerate(parts, start=1):
            title = f"{section['title']} (part {i})" if len(parts) > 1 else section["title"]
            notes.append({**section, "title": title, "body": part})
    if not notes:
        raise ValueError(f"{filename}: no text found (scanned PDFs can't be read)")
    return notes


def _section(title, body, tags="", kind="note", extra=None):
    return {"title": title, "body": body, "tags": tags, "kind": kind, "extra": extra or {}}


def _markdown_sections(text, fallback_title):
    """Split on "# Heading" lines. Also reads the app's own export (Type:/Tags: lines, steps, code)."""
    sections = []
    title, lines = fallback_title, []

    def finish():
        body_lines = [l for l in lines if l.strip() != "---"]
        details = {}
        # "Type: code", "Tags: a, b", "Language: python", "Deadline: ..." right under the heading
        while True:
            first = next((i for i, l in enumerate(body_lines) if l.strip()), None)
            match = first is not None and re.match(r"(Type|Tags|Language|Deadline): (.*)", body_lines[first])
            if not match:
                break
            details[match[1]] = match[2].strip()
            body_lines.pop(first)
        # the "*2026-10-28 08:55:04*" date line the export adds at the end
        last = next((i for i in reversed(range(len(body_lines))) if body_lines[i].strip()), None)
        if last is not None and re.fullmatch(r"\*\d{4}-\d\d-\d\d[^*]*\*", body_lines[last].strip()):
            body_lines.pop(last)

        kind = details.get("Type", "note")
        extra = {}
        if kind == "plan":
            steps = [re.match(r"\s*- \[( |x)\] (.*)", l) for l in body_lines]
            extra = {
                "steps": [{"text": m[2].strip(), "done": m[1] == "x"} for m in steps if m],
                "deadline": details.get("Deadline", ""),
            }
            body_lines = [l for l, m in zip(body_lines, steps) if not m]
        body = "\n".join(body_lines).strip()
        if kind == "code":
            body = re.sub(r"^```[\w+-]*\n|\n?```$", "", body)  # drop the ``` fences
            extra = {"language": details.get("Language", "other")}

        if body or kind in ("idea", "plan"):  # ideas and plans can be just a title
            sections.append(_section(title, body, details.get("Tags", ""), kind, extra))

    in_code = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if line.startswith("# ") and not in_code:  # a "# comment" inside code is not a heading
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
