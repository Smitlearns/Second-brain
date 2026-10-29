import json
from collections import Counter

import streamlit as st

from app import ai, database

FASTAPI_PORT = 8000  # where the Ask page runs (see run.py)

st.set_page_config(page_title="Second Brain", page_icon="🧠", layout="wide")
database.init_db()

# Remember which note is open, and whether it is being edited
st.session_state.setdefault("open_note", None)
st.session_state.setdefault("editing", False)


def open_note(note_id):
    st.session_state.open_note = note_id
    st.session_state.editing = False


@st.dialog("Delete this note?")
def confirm_delete(note_id):
    st.write("This can't be undone.")
    if st.button("Yes, delete"):
        database.delete_note(note_id)
        open_note(None)
        st.rerun()


def ask_link(note_id):
    """Link to the Ask page on the FastAPI server, which runs on another port."""
    host = st.context.headers.get("host", "127.0.0.1").split(":")[0]
    return f"http://{host}:{FASTAPI_PORT}/ask/note/{note_id}"


def show_body(note):
    if note["kind"] == "code":
        st.code(note["body"])
    else:
        st.write(note["body"])


def command_center(notes):
    stats = database.get_stats()
    cols = st.columns(5)
    cols[0].metric("Notes", stats["notes"])
    cols[1].metric("Added this week", stats["this_week"])
    cols[2].metric("Pinned", stats["pinned"])
    cols[3].metric("Chats", stats["chats"])
    cols[4].metric("Questions asked", stats["questions"])

    tag_counts = Counter(t for n in notes for t in n["tags"]).most_common(8)
    kind_counts = Counter(n["kind"] for n in notes)
    left, right = st.columns(2)
    left.caption("Top tags: " + ("  ".join(f"#{t} ({c})" for t, c in tag_counts) or "none yet"))
    right.caption("By type: " + "  ".join(
        f"{label} ({kind_counts[kind]})" for kind, label in database.KINDS.items() if kind_counts[kind]
    ))


def notes_tab(notes):
    search_col, tag_col, kind_col = st.columns([2, 2, 1])
    search = search_col.text_input("Search notes")
    picked = tag_col.multiselect("Filter by tag", database.get_all_tags())
    kind = kind_col.selectbox(
        "Type", ["all", *database.KINDS], format_func=lambda k: "All" if k == "all" else database.KINDS[k]
    )

    shown = database.search_notes(search) if search else notes
    if picked:
        shown = [n for n in shown if set(picked) <= set(n["tags"])]
    if kind != "all":
        shown = [n for n in shown if n["kind"] == kind]

    if not shown:
        st.info("No notes found.")

    for n in shown:
        with st.container(border=True):
            label = ("📌 " if n["pinned"] else "") + database.KINDS[n["kind"]].split()[0] + " " + n["title"]
            st.button(label, key=f"open{n['id']}", on_click=open_note, args=(n["id"],))
            preview = n["body"][:120] + ("..." if len(n["body"]) > 120 else "")
            st.caption(preview)
            if n["tags"]:
                st.caption(" ".join(f"#{t}" for t in n["tags"]))
            st.caption(n["created_at"])


def graph_tab(notes):
    if len(notes) < 2:
        st.info("Save a few notes to see how they connect.")
        return

    with st.spinner("Finding connections..."):
        links = ai.connections()

    colors = {"note": "#4f7cff", "idea": "#f2c94c", "plan": "#4caf7d", "code": "#bb6bd9"}
    nodes = [{
        "id": n["id"],
        "label": n["title"][:30],
        "title": f"{n['title']}\n{', '.join('#' + t for t in n['tags'])}",
        "color": colors[n["kind"]],
        "size": 22 if n["pinned"] else 14,
    } for n in notes]
    edges = [{"from": a, "to": b, "title": how, "dashes": how.startswith("similar")} for a, b, how in links]

    st.caption(
        f"{len(links)} connections. Solid lines share a tag, dashed lines mean similar content. "
        "Drag notes around, scroll to zoom, hover for details. Blue is a note, yellow an idea, "
        "green a plan, purple code. Pinned notes are bigger."
    )
    # "</" is escaped so a note title can't end the script tag early
    data = json.dumps({"nodes": nodes, "edges": edges}).replace("</", "<\\/")
    st.iframe(f"""
        <div id="graph" style="height:560px;background:#12141a;border-radius:10px"></div>
        <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
        <script>
            const data = {data};
            new vis.Network(document.getElementById("graph"), {{
                nodes: new vis.DataSet(data.nodes),
                edges: new vis.DataSet(data.edges),
            }}, {{
                nodes: {{ shape: "dot", font: {{ color: "#e6e6e6", size: 13 }} }},
                edges: {{ color: {{ color: "#555c70", highlight: "#8fa8ff" }}, smooth: false }},
                physics: {{ stabilization: {{ iterations: 200 }} }},
            }});
        </script>
    """, height=580)


def note_view(note):
    st.button("← Back to all notes", on_click=open_note, args=(None,))

    if st.session_state.editing:
        with st.form(f"edit_form_{note['id']}"):
            new_title = st.text_input("Title", value=note["title"])
            new_kind = st.selectbox(
                "Type", list(database.KINDS), index=list(database.KINDS).index(note["kind"]),
                format_func=database.KINDS.get,
            )
            new_body = st.text_area("Note", value=note["body"], height=250)
            new_tags = st.text_input("Tags, separated by commas", value=", ".join(note["tags"]))
            save = st.form_submit_button("Save changes")
            cancel = st.form_submit_button("Cancel")

        if save:
            if new_title.strip() and new_body.strip():
                database.update_note(note["id"], new_title.strip(), new_body.strip(), new_tags, new_kind)
                st.session_state.editing = False
                st.rerun()
            else:
                st.error("The title and the note can't be empty.")
        if cancel:
            st.session_state.editing = False
            st.rerun()
        return

    st.caption(database.KINDS[note["kind"]] + ("  ·  📌 Pinned" if note["pinned"] else ""))
    st.header(note["title"])
    show_body(note)
    if note["tags"]:
        st.caption(" ".join(f"#{t}" for t in note["tags"]))
    st.caption(f"Saved: {note['created_at']}")

    col_edit, col_pin, col_ask, col_delete, _ = st.columns([1, 1, 2, 1, 3])
    if col_edit.button("Edit"):
        st.session_state.editing = True
        st.rerun()
    if col_pin.button("Unpin" if note["pinned"] else "Pin"):
        database.set_pinned(note["id"], not note["pinned"])
        st.rerun()
    # target="_top" opens the Ask page in the whole window, not inside the Dashboard frame
    col_ask.markdown(
        f'<a href="{ask_link(note["id"])}" target="_top" class="ask-link">💬 Ask about this note</a>',
        unsafe_allow_html=True,
    )
    if col_delete.button("Delete"):
        confirm_delete(note["id"])

    related = ai.related_notes(note["id"])
    if related:
        st.subheader("Related notes")
        for r in related:
            st.button(f"{database.KINDS[r['kind']].split()[0]} {r['title']}", key=f"rel{r['id']}",
                      on_click=open_note, args=(r["id"],))


st.markdown("""
    <style>
    .ask-link { display: inline-block; padding: 0.4rem 0.75rem; border-radius: 0.5rem;
                background: #4f7cff; color: white !important; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

st.title("Second Brain")

note = database.get_note(st.session_state.open_note) if st.session_state.open_note else None
if note is None:
    open_note(None)
    notes = database.get_notes()
    command_center(notes)
    tab_notes, tab_graph = st.tabs(["Notes", "Graph"])
    with tab_notes:
        notes_tab(notes)
    with tab_graph:
        graph_tab(notes)
else:
    note_view(note)
