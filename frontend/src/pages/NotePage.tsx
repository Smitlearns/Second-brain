import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import * as api from "../api";
import type { Note, NoteFields } from "../api";
import { CodeBlock, Markdown, noteLabel, noteLink, Progress, Steps, Tags } from "../components/bits";
import NoteForm from "../components/NoteForm";
import { codeLanguage, deadlineText, fieldsFrom, KIND_LIST, KINDS, planProgress } from "../notes";

/** One note, laid out for its type, with edit, pin, delete and "Ask about this note". */
export default function NotePage() {
  const id = Number(useParams().noteId);
  const navigate = useNavigate();
  const location = useLocation();
  const [note, setNote] = useState<Note | null>(null);
  const [missing, setMissing] = useState(false);
  const [related, setRelated] = useState<Note[]>([]);
  const [editing, setEditing] = useState<NoteFields | null>(null);
  const [problem, setProblem] = useState("");

  useEffect(() => {
    let cancelled = false; // a slow answer for the previous note mustn't show up on this one
    setNote(null);
    setEditing(null);
    setMissing(false);
    api.getNote(id).then((n) => !cancelled && setNote(n), () => !cancelled && setMissing(true));
    setRelated([]);
    api.getRelated(id).then((r) => !cancelled && setRelated(r), () => {});
    return () => {
      cancelled = true;
    };
  }, [id]);

  // go back to the Dashboard section you came from, or the Dashboard if you opened this link directly
  const back = () => (location.key === "default" ? navigate("/dashboard") : navigate(-1));

  if (missing) return <main><p className="error">This note doesn't exist any more.</p><Link to="/dashboard">Back to the Dashboard</Link></main>;
  if (!note) return <main><p className="empty">Loading...</p></main>;

  async function save() {
    if (!editing) return;
    try {
      setNote(await api.updateNote(id, editing));
      setEditing(null);
      setProblem("");
    } catch (e) {
      setProblem((e as Error).message);
    }
  }

  async function remove() {
    if (!confirm("Delete this note? This can't be undone.")) return;
    await api.deleteNote(id);
    back();
  }

  async function askAbout() {
    navigate(`/ask/${(await api.chatAboutNote(id)).id}`);
  }

  return (
    <main>
      <button type="button" className="link" onClick={back}>← Back to all notes</button>

      {editing ? (
        <>
          {problem && <p className="error">{problem}</p>}
          <label className="field">Type
            <select value={editing.kind} onChange={(e) => setEditing({ ...editing, kind: e.target.value as Note["kind"] })}>
              {KIND_LIST.map((k) => <option key={k} value={k}>{KINDS[k].icon} {KINDS[k].label}</option>)}
            </select>
          </label>
          <NoteForm fields={editing} onChange={setEditing} onSubmit={save} submitLabel="Save changes"
            onCancel={() => setEditing(null)} />
        </>
      ) : (
        <>
          <small>{KINDS[note.kind].icon} {KINDS[note.kind].label}{note.pinned && "  ·  📌 Pinned"}</small>
          <NoteBody note={note} onChange={setNote} />
          <Tags tags={note.tags} />
          <small>Saved: {note.created_at}</small>

          <div className="buttons">
            <button type="button" className="secondary" onClick={() => setEditing(fieldsFrom(note))}>Edit</button>
            <button type="button" className="secondary" onClick={() => api.setPinned(id, !note.pinned).then(setNote)}>
              {note.pinned ? "Unpin" : "Pin"}
            </button>
            <button type="button" onClick={askAbout}>💬 Ask about this note</button>
            <button type="button" className="delete" onClick={remove}>Delete</button>
          </div>

          {related.length > 0 && (
            <section>
              <h2>Related notes</h2>
              <div className="stack">
                {related.map((r) => <Link key={r.id} to={noteLink(r.id)}>{noteLabel(r)}</Link>)}
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}

function NoteBody({ note, onChange }: { note: Note; onChange: (note: Note) => void }) {
  if (note.kind === "idea") {
    return (
      <>
        <h1>💡 {note.title}</h1>
        {note.body && <div className="card kind-idea"><strong>Why it matters</strong><Markdown text={note.body} /></div>}
      </>
    );
  }

  if (note.kind === "plan") {
    const { done, total } = planProgress(note);
    const due = deadlineText(note);
    return (
      <>
        <h1>{note.title}</h1>
        <div className="metrics">
          <div className="metric"><small>Steps done</small><strong>{total ? `${done}/${total}` : "No steps"}</strong></div>
          <div className="metric"><small>Deadline</small><strong>{note.extra.deadline || "None"}</strong></div>
          {due && <div className="metric"><small>Time left</small><strong>{due.replace("due ", "")}</strong></div>}
        </div>
        {total > 0 && <><Progress done={done} total={total} /><Steps note={note} onChange={onChange} /></>}
        {note.body && <><strong>Details</strong><Markdown text={note.body} /></>}
      </>
    );
  }

  if (note.kind === "code") {
    return (
      <>
        <h1>{note.title}</h1>
        <small>Language: {codeLanguage(note)}</small>
        <CodeBlock code={note.body} />
      </>
    );
  }

  return (
    <>
      <h1>{note.title}</h1>
      <Markdown text={note.body} />
    </>
  );
}
