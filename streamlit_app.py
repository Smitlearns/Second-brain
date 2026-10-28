import streamlit as st

from app import database

st.set_page_config(page_title="Second Brain", page_icon="🧠", layout="wide")
database.init_db()

# Remember which note is open, and whether it is being edited
st.session_state.setdefault("open_note", None)
st.session_state.setdefault("editing", False)


@st.dialog("Delete this note?")
def confirm_delete(note_id):
    st.write("This can't be undone.")
    if st.button("Yes, delete"):
        database.delete_note(note_id)
        st.session_state.open_note = None
        st.session_state.editing = False
        st.rerun()


st.title("Second Brain")

note = None
if st.session_state.open_note is not None:
    note = database.get_note(st.session_state.open_note)

if note is None:
    # ---------- List view ----------
    st.session_state.open_note = None
    st.session_state.editing = False

    notes = database.get_notes()
    col1, col2, col3 = st.columns([1, 2, 1])
    col1.metric("Total notes", len(notes))
    col2.metric("Latest note", notes[0]["title"] if notes else "None yet")
    col3.button("Refresh")  # any click reloads the notes from the database

    search = st.text_input("Search notes")
    shown = database.search_notes(search) if search else notes

    if not shown:
        st.info("No notes found.")

    for n in shown:
        with st.container(border=True):
            if st.button(n["title"], key=f"open{n['id']}"):
                st.session_state.open_note = n["id"]
                st.rerun()
            preview = n["body"][:120] + ("..." if len(n["body"]) > 120 else "")
            st.caption(preview)
            st.caption(n["created_at"])

else:
    # ---------- Single note view ----------
    if st.button("← Back to all notes"):
        st.session_state.open_note = None
        st.session_state.editing = False
        st.rerun()

    if st.session_state.editing:
        with st.form(f"edit_form_{note['id']}"):
            new_title = st.text_input("Title", value=note["title"])
            new_body = st.text_area("Note", value=note["body"], height=250)
            save = st.form_submit_button("Save changes")
            cancel = st.form_submit_button("Cancel")

        if save:
            if new_title.strip() and new_body.strip():
                database.update_note(note["id"], new_title.strip(), new_body.strip())
                st.session_state.editing = False
                st.rerun()
            else:
                st.error("The title and the note can't be empty.")
        if cancel:
            st.session_state.editing = False
            st.rerun()
    else:
        st.header(note["title"])
        st.write(note["body"])
        st.caption(f"Saved: {note['created_at']}")

        col_edit, col_delete, _ = st.columns([1, 1, 6])
        if col_edit.button("Edit"):
            st.session_state.editing = True
            st.rerun()
        if col_delete.button("Delete"):
            confirm_delete(note["id"])