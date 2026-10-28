import streamlit as st

from app import ai, database

st.set_page_config(page_title="Second Brain", page_icon="🧠")
st.title("Second Brain")

database.init_db()

tab_ask, tab_notes = st.tabs(["Ask", "Notes"])

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

with tab_notes:
    with st.form("add_note", clear_on_submit=True):
        title = st.text_input("Title")
        body = st.text_area("Note")
        if st.form_submit_button("Save note") and title and body:
            database.add_note(title, body)
            st.success("Saved")

    search = st.text_input("Search notes")
    notes = database.search_notes(search) if search else database.get_notes()

    for note in notes:
        with st.expander(note["title"]):
            st.write(note["body"])
            st.caption(note["created_at"])
            if st.button("Delete", key=f"del{note['id']}"):
                database.delete_note(note["id"])
                st.rerun()