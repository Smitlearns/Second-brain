import logging
import math
import re

import httpx
import ollama

from app import database

MODEL = "llama3.2:3b"
EMBED_MODEL = "nomic-embed-text"  # turns text into numbers so we can compare meaning

# Errors that mean Ollama isn't running or the model isn't downloaded
AI_ERRORS = (ollama.ResponseError, ConnectionError, httpx.HTTPError)

# How similar (0 to 1) notes must be to count as a match. Tune these if results feel off.
MIN_QUESTION_MATCH = 0.45
MIN_RELATED_MATCH = 0.55

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "and", "what", "how", "why", "does", "are", "for", "with", "this",
    "that", "you", "can", "from", "about", "into", "tell", "explain", "give",
    "when", "which", "who", "was", "were", "has", "have", "had", "not", "but",
    "its", "any", "all", "your", "our", "get", "make", "between", "difference",
    "note", "notes", "summarize", "quiz", "questions", "simply",
}


# ---------- Embeddings ----------

def _note_text(note):
    # nomic-embed-text works best when told whether text is a document or a question
    return f"search_document: {note['title']}\n{' '.join(note['tags'])}\n{database.full_text(note)}"


def _for_prompt(note):
    kind = database.KINDS[note["kind"]].split()[-1]  # "Plan", "Code", ...
    return f"{kind}: {note['title']}\n{database.full_text(note)}"


def ensure_embeddings():
    """Work out the meaning of any new or edited notes. Returns {note_id: vector}, or {} if Ollama is off."""
    missing = database.get_notes_without_embedding()
    try:
        if missing:
            response = ollama.embed(model=EMBED_MODEL, input=[_note_text(n) for n in missing])
            for note, vector in zip(missing, response.embeddings):
                database.set_embedding(note["id"], vector)
    except AI_ERRORS:
        logger.warning("Embeddings unavailable, falling back to keyword search", exc_info=True)
        return {}
    return database.get_embeddings()


def similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    size = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / size if size else 0.0


# ---------- Finding notes ----------

def _keywords(text):
    return {
        w for w in re.findall(r"[a-z0-9]+", text.lower())
        if len(w) > 2 and w not in STOPWORDS
    }


def _keyword_hits(words, note):
    text = " ".join([note["title"], database.full_text(note), *note["tags"]]).lower()
    return sum(1 for w in words if w in text)


def find_relevant_notes(question, limit=3):
    """Find notes that mean the same thing as the question, with a small bonus for exact words."""
    words = _keywords(question)
    vectors = ensure_embeddings()
    notes = database.get_notes()

    if vectors:
        try:
            q = ollama.embed(model=EMBED_MODEL, input="search_query: " + question).embeddings[0]
        except AI_ERRORS:
            vectors = {}

    scored = []
    for note in notes:
        hits = _keyword_hits(words, note)
        if vectors and note["id"] in vectors:
            meaning = similarity(q, vectors[note["id"]])
            if meaning >= MIN_QUESTION_MATCH or hits:
                scored.append((meaning + 0.05 * hits, note))
        elif hits:
            scored.append((hits, note))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [note for _, note in scored[:limit]]


def related_notes(note_id, limit=3):
    """Notes that are about something similar. Falls back to shared tags if Ollama is off."""
    note = database.get_note(note_id)
    if note is None:
        return []
    others = [n for n in database.get_notes() if n["id"] != note_id]
    vectors = ensure_embeddings()

    if vectors and note_id in vectors:
        scored = [
            (similarity(vectors[note_id], vectors[n["id"]]), n)
            for n in others if n["id"] in vectors
        ]
        scored = [pair for pair in scored if pair[0] >= MIN_RELATED_MATCH]
    else:
        scored = [(len(set(note["tags"]) & set(n["tags"])), n) for n in others]
        scored = [pair for pair in scored if pair[0]]

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [n for _, n in scored[:limit]]


def connections():
    """Every pair of notes that is linked, for the knowledge graph: (id_a, id_b, how)."""
    notes = database.get_notes()
    vectors = ensure_embeddings()
    links = []
    for i, a in enumerate(notes):
        for b in notes[i + 1:]:
            shared = set(a["tags"]) & set(b["tags"])
            if shared:
                links.append((a["id"], b["id"], "tag: " + ", ".join(sorted(shared))))
            elif a["id"] in vectors and b["id"] in vectors:
                score = similarity(vectors[a["id"]], vectors[b["id"]])
                if score >= MIN_RELATED_MATCH:
                    links.append((a["id"], b["id"], f"similar ({score:.0%})"))
    return links


# ---------- Answering ----------

def prepare(question, history=None, focus_note=None):
    """Pick the notes for this question and build the messages for the model."""
    history = history or []

    # Include the previous question so follow-ups like "explain more" still find the right notes
    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    # In a chat about one note, search with its title, since questions like "summarize this" have no topic
    topic = focus_note["title"] if focus_note else last_user
    notes = find_relevant_notes(question + " " + topic)

    system_prompt = (
        "You are a study helper inside the user's personal notes app. "
        "Answer using the notes below when they are relevant. "
        "If the notes don't cover the question, say so briefly, "
        "then give a short general answer. "
        "Answer in at most 4 short sentences.\n\n"
    )

    if focus_note:
        # The note this chat is about always comes first, marked so "this note" means it
        notes = [focus_note] + [n for n in notes if n["id"] != focus_note["id"]][:2]
        system_prompt += (
            "This chat is about ONE note. When the user says \"this note\", they mean this one:\n"
            f"{_for_prompt(focus_note)}\n\n"
        )
        others = notes[1:]
    else:
        others = notes

    if others:
        context = "\n\n".join(_for_prompt(n) for n in others)
    else:
        context = "(no matching notes)"
    system_prompt += ("OTHER NOTES that may help:\n" if focus_note else "NOTES:\n") + context

    messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": question})
    return messages, [n["title"] for n in notes]


def make_title(question, answer):
    """A short name for a chat, written by the model from its first question and answer."""
    response = ollama.chat(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": (
                "Write a short title (2 to 6 words) for a chat that starts like this. "
                "Reply with only the title: no quotes, no full stop.\n\n"
                f"Question: {question}\nAnswer: {answer[:500]}"
            ),
        }],
        keep_alive="2m",
        options={"num_predict": 20, "temperature": 0.3},
    )
    lines = response.message.content.strip().splitlines()
    title = lines[0] if lines else ""
    title = re.sub(r"^(title|chat title)\s*:\s*", "", title, flags=re.IGNORECASE)
    title = title.strip(" \"'*#.").strip()
    return title[:50]


def stream_answer(messages):
    """Yield the answer a few words at a time, as the model writes it."""
    for chunk in ollama.chat(
        model=MODEL,
        messages=messages,
        stream=True,
        keep_alive="2m",  # unload the model from RAM 2 minutes after the last question
        options={"num_predict": 200},  # stop after about 200 tokens
    ):
        yield chunk.message.content
