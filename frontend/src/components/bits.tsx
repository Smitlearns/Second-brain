import ReactMarkdown from "react-markdown";
import { Link } from "react-router-dom";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import { setStepDone, type Note } from "../api";
import { deadlineText, fullDate, planFinished, planProgress, preview, shortDate } from "../notes";
import { NoteLabel } from "./icons";

/** Note text or an AI answer as Markdown. A single Enter still starts a new line, as in plain text. */
export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{ a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer" /> }}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

export function Progress({ done, total, text }: { done: number; total: number; text?: string }) {
  return (
    <div className="progress">
      <progress value={done} max={total} aria-label="Steps done" />
      {text && <small>{text}</small>}
    </div>
  );
}

export function Tags({ tags }: { tags: string[] }) {
  return tags.length ? <div className="chips">{tags.map((t) => <span key={t} className="chip">#{t}</span>)}</div> : null;
}

/** Plan steps you can tick. onChange gets the note back with the step saved. */
export function Steps({ note, onChange }: { note: Note; onChange: (note: Note) => void }) {
  return (
    <ul className="steps">
      {(note.extra.steps ?? []).map((step, i) => (
        <li key={i}>
          <label>
            <input type="checkbox" checked={step.done}
              onChange={(e) => setStepDone(note.id, i, e.target.checked).then(onChange)} />
            <span className={step.done ? "done" : undefined}>{step.text}</span>
          </label>
        </li>
      ))}
    </ul>
  );
}

/** The bottom line of a card: tags on the left, the date on the right. */
export function CardMeta({ note }: { note: Note }) {
  return (
    <div className="card-meta">
      {note.tags.map((t) => <span key={t} className="chip">#{t}</span>)}
      <small className="date" title={fullDate(note.created_at)}>{shortDate(note.created_at)}</small>
    </div>
  );
}

export const noteLink = (id: number) => `/dashboard/notes/${id}`;

/** One note in a list. Each type shows what matters most for it. */
export function NoteCard({ note: n }: { note: Note }) {
  const { done, total } = planProgress(n);
  const due = deadlineText(n);
  const steps = planFinished(n) ? "All steps done" : `${done}/${total} steps done`;
  return (
    <article className={`card note-card kind-${n.kind}`}>
      <Link to={noteLink(n.id)} className="card-title"><NoteLabel note={n} /></Link>
      {n.kind === "idea" && n.body && <p className="card-text">{preview(n.body)}</p>}
      {n.kind === "plan" && (total
        ? <Progress done={done} total={total} text={`${steps}${due ? ` · ${due}` : ""}`} />
        : due && <small>{due}</small>)}
      {n.kind === "note" && <p className="card-text">{preview(n.body)}</p>}
      <CardMeta note={n} />
    </article>
  );
}
