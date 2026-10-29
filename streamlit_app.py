import json
from collections import Counter
from datetime import date

import streamlit as st

from app import ai, database

FASTAPI_PORT = 8000  # where the Ask page runs (see run.py)

st.set_page_config(page_title="Second Brain", page_icon="🧠", layout="wide")
database.init_db()

# Remember which note is open, and whether it is being edited
st.session_state.setdefault("open_note", None)
st.session_state.setdefault("editing", False)
st.session_state.setdefault("section", "🗂️ All")


def remember_section():
    # clicking the section that's already selected unselects it, so ignore that
    if st.session_state.section_picker:
        st.session_state.section = st.session_state.section_picker


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


# ---------- How each type of note looks ----------

TITLE_LABELS = {"note": "Title", "idea": "Your idea in one line", "plan": "Goal", "code": "What does this code do?"}
BODY_LABELS = {"note": "Note", "idea": "Why it matters (optional)", "plan": "Details (optional)", "code": "Code"}


def preview(text, length=120):
    return text[:length] + ("..." if len(text) > length else "")


def code_language(note):
    lang = note["extra"].get("language")
    return None if lang in (None, "other") else lang


def plan_progress(note):
    steps = note["extra"].get("steps", [])
    return sum(s["done"] for s in steps), len(steps)


def deadline_text(note):
    deadline = note["extra"].get("deadline")
    if not deadline:
        return ""
    try:
        days = (date.fromisoformat(deadline) - date.today()).days
    except ValueError:
        return f"due {deadline}"
    if days > 1:
        return f"due in {days} days"
    if days == 1:
        return "due tomorrow"
    if days == 0:
        return "due today"
    return f"overdue by {-days} day{'s' if days < -1 else ''}"


def note_card(n, where="all"):
    """One note in the list. Each type shows what matters most for it."""
    with st.container(border=True):
        label = ("📌 " if n["pinned"] else "") + database.KINDS[n["kind"]].split()[0] + " " + n["title"]
        st.button(label, key=f"open{where}{n['id']}", on_click=open_note, args=(n["id"],))

        if n["kind"] == "idea":
            if n["body"]:
                st.caption("Why it matters: " + preview(n["body"]))
        elif n["kind"] == "plan":
            done, total = plan_progress(n)
            due = deadline_text(n)
            if total:
                st.progress(done / total, text=f"{done}/{total} steps done" + (f" · {due}" if due else ""))
            elif due:
                st.caption(due)
        elif n["kind"] == "code":
            lines = n["body"].splitlines()
            st.code("\n".join(lines[:4]) + ("\n..." if len(lines) > 4 else ""), language=code_language(n))
        else:
            st.caption(preview(n["body"]))

        if n["tags"]:
            st.caption(" ".join(f"#{t}" for t in n["tags"]))
        st.caption(n["created_at"])


def toggle_step(note_id, index, key):
    database.set_step_done(note_id, index, st.session_state[key])


def step_checkboxes(note, prefix):
    for i, step in enumerate(note["extra"]["steps"]):
        key = f"{prefix}{note['id']}_{i}"
        st.checkbox(step["text"], value=step["done"], key=key, on_change=toggle_step, args=(note["id"], i, key))


def show_note(note):
    """The full page for one note, laid out for its type."""
    kind = note["kind"]
    if kind == "idea":
        st.markdown(f"## 💡 {note['title']}")
        if note["body"]:
            with st.container(border=True):
                st.markdown("**Why it matters**")
                st.write(note["body"])

    elif kind == "plan":
        st.header(note["title"])
        done, total = plan_progress(note)
        due = deadline_text(note)
        cols = st.columns(3)
        cols[0].metric("Steps done", f"{done}/{total}" if total else "No steps")
        cols[1].metric("Deadline", note["extra"].get("deadline") or "None")
        if due:
            cols[2].metric("Time left", due.replace("due ", "").capitalize())
        if total:
            st.progress(done / total)
            step_checkboxes(note, "step")
        if note["body"]:
            st.markdown("**Details**")
            st.write(note["body"])

    elif kind == "code":
        st.header(note["title"])
        st.caption(f"Language: {note['extra'].get('language', 'other')}")
        st.code(note["body"], language=code_language(note), line_numbers=True)

    else:
        st.header(note["title"])
        st.write(note["body"])


def edit_form(note):
    """Edit a note. The fields change with the type picked above the form."""
    kinds = list(database.KINDS)
    kind = st.selectbox("Type", kinds, index=kinds.index(note["kind"]), format_func=database.KINDS.get,
                        key=f"edit_kind_{note['id']}")
    extra = note["extra"]

    with st.form(f"edit_form_{note['id']}"):
        new_title = st.text_input(TITLE_LABELS[kind], value=note["title"])
        steps, deadline, language = "", None, ""
        if kind == "code":
            langs = database.LANGUAGES
            current = extra.get("language", "other")
            language = st.selectbox("Language", langs, index=langs.index(current) if current in langs else len(langs) - 1)
        if kind == "plan":
            steps = st.text_area("Steps, one per line", value="\n".join(s["text"] for s in extra.get("steps", [])))
            try:
                old_deadline = date.fromisoformat(extra["deadline"]) if extra.get("deadline") else None
            except ValueError:
                old_deadline = None
            deadline = st.date_input("Deadline (optional)", value=old_deadline)
        new_body = st.text_area(BODY_LABELS[kind], value=note["body"], height=250 if kind in ("note", "code") else 120)
        new_tags = st.text_input("Tags, separated by commas", value=", ".join(note["tags"]))
        save = st.form_submit_button("Save changes")
        cancel = st.form_submit_button("Cancel")

    if save:
        # ideas and plans can be saved without a body, notes and code can't
        if not new_title.strip() or (kind in ("note", "code") and not new_body.strip()):
            st.error(f"Please fill in the {TITLE_LABELS[kind].lower()} and the {BODY_LABELS[kind].lower()}.")
        else:
            new_extra = database.make_extra(kind, steps, deadline.isoformat() if deadline else "", language,
                                            old_steps=extra.get("steps"))
            database.update_note(note["id"], new_title.strip(), new_body.strip(), new_tags, kind, new_extra)
            st.session_state.editing = False
            st.rerun()
    if cancel:
        st.session_state.editing = False
        st.rerun()


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


# ---------- One section per type, each with its own layout ----------

def all_tab(notes):
    search_col, tag_col = st.columns(2)
    search = search_col.text_input("Search everything")
    picked = tag_col.multiselect("Filter by tag", database.get_all_tags())

    shown = database.search_notes(search) if search else notes
    if picked:
        shown = [n for n in shown if set(picked) <= set(n["tags"])]

    if not shown:
        st.info("No notes found.")

    cols = st.columns(2)
    for i, n in enumerate(shown):
        with cols[i % 2]:
            note_card(n)


def empty(kind):
    st.info(f"No {kind}s yet. Add one on the Notes tab at the top of the app.")


def notes_only_tab(notes):
    plain = [n for n in notes if n["kind"] == "note"]
    if not plain:
        return empty("note")
    cols = st.columns(2)
    for i, n in enumerate(plain):
        with cols[i % 2]:
            note_card(n, "notes")


def ideas_tab(notes):
    # quick add, so an idea can be saved without leaving the Dashboard
    with st.form("quick_idea", clear_on_submit=True, border=False):
        text_col, button_col = st.columns([5, 1], vertical_alignment="bottom")
        idea = text_col.text_input("New idea", placeholder="Got an idea? Type it in one line")
        if button_col.form_submit_button("Add idea") and idea.strip():
            database.add_note(idea.strip(), "", "", "idea")
            st.rerun()

    ideas = [n for n in notes if n["kind"] == "idea"]
    if not ideas:
        return st.info("No ideas yet. Type one above.")
    cols = st.columns(3)
    for i, n in enumerate(ideas):
        with cols[i % 3], st.container(border=True):
            st.markdown(f"#### {'📌 ' if n['pinned'] else ''}💡 {n['title']}")
            if n["body"]:
                st.caption(preview(n["body"], 150))
            st.button("Open", key=f"openidea{n['id']}", on_click=open_note, args=(n["id"],))


def plans_tab(notes):
    plans = [n for n in notes if n["kind"] == "plan"]
    if not plans:
        return empty("plan")

    def order(n):  # unfinished plans first, soonest deadline first
        done, total = plan_progress(n)
        return (total > 0 and done == total, n["extra"].get("deadline") or "9999")

    for n in sorted(plans, key=order):
        done, total = plan_progress(n)
        due = deadline_text(n)
        with st.container(border=True):
            title_col, button_col = st.columns([5, 1])
            finished = " ✅" if total and done == total else ""
            title_col.markdown(f"#### 🗺️ {n['title']}{finished}")
            button_col.button("Open", key=f"openplan{n['id']}", on_click=open_note, args=(n["id"],))
            if total:
                st.progress(done / total, text=f"{done}/{total} steps done")
            if due:
                st.caption(f":red[{due}]" if due.startswith("overdue") else due)
            if total:
                with st.expander("Steps"):
                    step_checkboxes(n, "planstep")


def code_tab(notes):
    snippets = [n for n in notes if n["kind"] == "code"]
    if not snippets:
        return empty("code snippet")

    langs = sorted({n["extra"].get("language", "other") for n in snippets})
    if len(langs) > 1:
        picked = st.pills("Language", langs)
        if picked:
            snippets = [n for n in snippets if n["extra"].get("language", "other") == picked]

    for n in snippets:
        with st.expander(f"💻 {n['title']}  ·  {n['extra'].get('language', 'other')}"):
            st.code(n["body"], language=code_language(n), line_numbers=True)
            if n["tags"]:
                st.caption(" ".join(f"#{t}" for t in n["tags"]))
            st.button("Open", key=f"opencode{n['id']}", on_click=open_note, args=(n["id"],))


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
        edit_form(note)
        return

    st.caption(database.KINDS[note["kind"]] + ("  ·  📌 Pinned" if note["pinned"] else ""))
    show_note(note)
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

    sections = {
        "🗂️ All": all_tab,
        "📝 Notes": notes_only_tab,
        "💡 Ideas": ideas_tab,
        "🗺️ Plans": plans_tab,
        "💻 Code": code_tab,
        "🕸️ Graph": graph_tab,
    }
    # Streamlit forgets a widget's value while a note is open, so the section is also
    # kept in "section". That way "Back" returns to the same section.
    st.session_state.section_picker = st.session_state.section
    st.segmented_control("Section", list(sections), key="section_picker",
                         on_change=remember_section, label_visibility="collapsed")
    sections[st.session_state.section](notes)
else:
    note_view(note)
