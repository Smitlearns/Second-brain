import re

import ollama

from app import database

MODEL = "llama3.2:3b"

STOPWORDS = {
    "the", "and", "what", "how", "why", "does", "are", "for", "with", "this",
    "that", "you", "can", "from", "about", "into", "tell", "explain", "give",
    "when", "which", "who", "was", "were", "has", "have", "had", "not", "but",
    "its", "any", "all", "your", "our", "get", "make", "between", "difference",
}


def find_relevant_notes(question, limit=3):
    """Score every note by how many question words it contains."""
    words = {
        w for w in re.findall(r"[a-z0-9]+", question.lower())
        if len(w) > 2 and w not in STOPWORDS
    }
    scored = []
    for note in database.get_notes():
        text = (note["title"] + " " + note["body"]).lower()
        score = sum(1 for w in words if w in text)
        if score:
            scored.append((score, note))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [note for _, note in scored[:limit]]


def ask_brain(question):
    notes = find_relevant_notes(question)
    if notes:
        context = "\n\n".join(f"Title: {n['title']}\n{n['body']}" for n in notes)
    else:
        context = "(no matching notes)"

    system_prompt = (
        "You are a study helper inside the user's personal notes app. "
        "Answer using the notes below when they are relevant. "
        "If the notes don't cover the question, say so briefly, "
        "then give a short general answer. "
        "Answer in at most 4 short sentences.\n\n"
        "NOTES:\n" + context
    )

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        keep_alive="2m",  # unload the model from RAM 2 minutes after the last question
        options={"num_predict": 200},  # stop after about 200 tokens
    )
    return response.message.content, [n["title"] for n in notes]