import streamlit as st

from app import ai, database

st.set_page_config(page_title="Second Brain", page_icon="🧠", layout="wide")
database.init_db()

st.title("Second Brain")

tab_notes, tab_ask, tab_add = st.tabs(["Notes", "Ask", "Add note"])

# This tab comes first in the code, so a new note is saved before the list loads
with tab_add:
    with st.form("add_note", clear_on_submit=True):
        title = st.text_input("Title")
        body = st.text_area("Note")
        if st.form_submit_button("Save note") and title and body:
            database.add_note(title, body)
            st.success("Saved. Open the Notes tab to see it.")

notes = database.get_notes()

with tab_notes:
    col1, col2, col3 = st.columns([1, 2, 1])
    col1.metric("Total notes", len(notes))
    col2.metric("Latest note", notes[0]["title"] if notes else "None yet")
    col3.button("Refresh")  # any click reloads the notes from the database

    search = st.text_input("Search notes")
    shown = database.search_notes(search) if search else notes

    if not shown:
        st.info("No notes found.")

    for note in shown:
        with st.container(border=True):
            st.subheader(note["title"])
            st.write(note["body"])
            st.caption(note["created_at"])
            if st.button("Delete", key=f"del{note['id']}"):
                database.delete_note(note["id"])
                st.rerun()

with tab_ask:
    question = st.text_input("Ask your brain...")
    if st.button("Ask") and question:
        with st.spinner("Thinking..."):
            try:
                answer, sources = ai.ask_brain(question)
                st.write(answer)
                if sources:
                    st.caption("From your notes: " + ", ".join(sources))
            except Exception:
                st.error("Couldn't reach the AI model. Is Ollama running?")