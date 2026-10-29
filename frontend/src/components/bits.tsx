import { Link } from "react-router-dom";
import { setStepDone, type Note } from "../api";
import { codeLanguage, deadlineText, KINDS, planProgress, preview } from "../notes";

export function Progress({ done, total, text }: { done: number; total: number; text?: string }) {
  return (
    <div className="progress">
      <progress value={done} max={total} aria-label="Steps done" />
      {text && <small>{text}</small>}
    </div>
  );
}

export function Tags({ tags }: { tags: string[] }) {
  return tags.length ? <small>{tags.map((t) => `#${t}`).join(" ")}</small> : null;
}

/** Code with line numbers. maxLines cuts it short for previews. */
export function CodeBlock({ code, maxLines }: { code: string; maxLines?: number }) {
  let lines = code.split("\n");
  const cut = maxLines !== undefined && lines.length > maxLines;
  if (cut) lines = lines.slice(0, maxLines);
  return (
    <pre className="code-block">
      <code>
        {lines.map((line, i) => (
          <span key={i} className="line">{maxLines === undefined && <span className="ln">{i + 1}</span>}{line}{"\n"}</span>
        ))}
        {cut && "..."}
      </code>
    </pre>
  );
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

export const noteLink = (id: number) => `/dashboard/notes/${id}`;

export const noteLabel = (n: Note) => `${n.pinned ? "📌 " : ""}${KINDS[n.kind].icon} ${n.title}`;

/** One note in a list. Each type shows what matters most for it. */
export function NoteCard({ note: n }: { note: Note }) {
  const { done, total } = planProgress(n);
  const due = deadlineText(n);
  return (
    <article className={`card note-card kind-${n.kind}`}>
      <Link to={noteLink(n.id)} className="card-title">{noteLabel(n)}</Link>
      {n.kind === "idea" && n.body && <small>Why it matters: {preview(n.body)}</small>}
      {n.kind === "plan" && (total
        ? <Progress done={done} total={total} text={`${done}/${total} steps done${due ? ` · ${due}` : ""}`} />
        : due && <small>{due}</small>)}
      {n.kind === "code" && <CodeBlock code={n.body} maxLines={4} />}
      {n.kind === "note" && <small>{preview(n.body)}</small>}
      {n.kind === "code" && <small>{codeLanguage(n)}</small>}
      <Tags tags={n.tags} />
      <small>{n.created_at}</small>
    </article>
  );
}
