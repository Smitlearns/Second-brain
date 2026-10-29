import { lazy, Suspense, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as api from "../api";
import type { Note, Stats } from "../api";
import { CodeBlock, NoteCard, noteLabel, noteLink, Progress, Steps, Tags } from "../components/bits";
// the graph library is big, so it only loads when the Graph section is opened
const Graph = lazy(() => import("../components/Graph"));
import { codeLanguage, deadlineText, DUE_SOON_DAYS, duePlans, KIND_LIST, KINDS, planProgress, preview } from "../notes";

const SECTIONS = {
  all: "🗂️ All",
  notes: "📝 Notes",
  ideas: "💡 Ideas",
  plans: "🗺️ Plans",
  code: "💻 Code",
  graph: "🕸️ Graph",
};
type Section = keyof typeof SECTIONS;

/** Every note, with a section per type. The section is kept in the URL, so "Back" returns to it. */
export default function DashboardPage() {
  const [params, setParams] = useSearchParams();
  const asked = params.get("section") ?? "";
  const section: Section = asked in SECTIONS ? (asked as Section) : "all";
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [failed, setFailed] = useState(false);

  function reload() {
    api.getNotes().then(setNotes, () => setFailed(true));
    api.getStats().then(setStats);
  }
  useEffect(reload, []);

  // a ticked step only changes one note, so swap it in without reloading everything
  const replaceNote = (note: Note) => setNotes((list) => list?.map((n) => (n.id === note.id ? note : n)) ?? null);

  if (failed) return <main className="wide"><p className="error">Couldn't load your notes. Is the server running?</p></main>;
  if (!notes) return <main className="wide"><p className="empty">Loading...</p></main>;

  const props = { notes, replaceNote, reload };
  return (
    <main className="wide">
      <h1>Second Brain</h1>
      {stats && <CommandCenter notes={notes} stats={stats} />}
      <DueSoon notes={notes} />

      <div className="pills" role="tablist" aria-label="Section">
        {(Object.keys(SECTIONS) as Section[]).map((s) => (
          <button key={s} type="button" role="tab" aria-selected={s === section}
            className={s === section ? "pill active" : "pill"}
            onClick={() => setParams(s === "all" ? {} : { section: s }, { replace: true })}>
            {SECTIONS[s]}
          </button>
        ))}
      </div>

      {section === "notes" && <NotesOnly {...props} />}
      {section === "ideas" && <Ideas {...props} />}
      {section === "plans" && <Plans {...props} />}
      {section === "code" && <CodeSnippets {...props} />}
      {section === "graph" && <Suspense fallback={<p className="empty">Loading graph...</p>}><Graph notes={notes} /></Suspense>}
      {section === "all" && <All {...props} />}
    </main>
  );
}

interface SectionProps {
  notes: Note[];
  replaceNote: (note: Note) => void;
  reload: () => void;
}

function CommandCenter({ notes, stats }: { notes: Note[]; stats: Stats }) {
  const tagCounts = new Map<string, number>();
  notes.flatMap((n) => n.tags).forEach((t) => tagCounts.set(t, (tagCounts.get(t) ?? 0) + 1));
  const topTags = [...tagCounts].sort((a, b) => b[1] - a[1]).slice(0, 8);
  const byKind = KIND_LIST.map((k) => [k, notes.filter((n) => n.kind === k).length] as const).filter(([, c]) => c);

  const metrics: [string, number][] = [
    ["Notes", stats.notes],
    ["Added this week", stats.this_week],
    ["Pinned", stats.pinned],
    ["Chats", stats.chats],
    ["Questions asked", stats.questions],
  ];
  return (
    <>
      <div className="metrics">
        {metrics.map(([label, value]) => (
          <div key={label} className="metric"><small>{label}</small><strong>{value}</strong></div>
        ))}
      </div>
      <div className="split">
        <small>Top tags: {topTags.map(([t, c]) => `#${t} (${c})`).join("  ") || "none yet"}</small>
        <small>By type: {byKind.map(([k, c]) => `${KINDS[k].icon} ${KINDS[k].label} (${c})`).join("  ")}</small>
      </div>
    </>
  );
}

/** Plans that are overdue or due in the next few days, so they're seen before anything else. */
function DueSoon({ notes }: { notes: Note[] }) {
  const due = duePlans(notes);
  if (!due.length) return null;
  return (
    <section className="card due-soon" aria-label="Plans due soon">
      <strong>⏰ Due in the next {DUE_SOON_DAYS} days or overdue</strong>
      <ul>
        {due.map((n) => {
          const text = deadlineText(n);
          const { done, total } = planProgress(n);
          return (
            <li key={n.id}>
              <Link to={noteLink(n.id)}>{n.title}</Link>{" "}
              <small className={text.startsWith("overdue") ? "error" : undefined}>{text}</small>
              {total > 0 && <small> · {done}/{total} steps done</small>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Empty({ what }: { what: string }) {
  return <p className="empty">No {what}s yet. Add one on the <Link to="/">Notes</Link> page.</p>;
}

function All({ notes }: SectionProps) {
  const [search, setSearch] = useState("");
  const [found, setFound] = useState<Note[] | null>(null);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [picked, setPicked] = useState<string[]>([]);

  useEffect(() => {
    api.getTags().then(setAllTags);
  }, [notes]);

  useEffect(() => {
    if (!search.trim()) return setFound(null);
    // wait until typing pauses, instead of searching on every key
    const timer = setTimeout(() => api.searchNotes(search.trim()).then(setFound), 250);
    return () => clearTimeout(timer);
  }, [search]);

  const shown = (found ?? notes).filter((n) => picked.every((t) => n.tags.includes(t)));
  const toggleTag = (t: string) => setPicked((p) => (p.includes(t) ? p.filter((x) => x !== t) : [...p, t]));

  return (
    <>
      <input type="search" value={search} onChange={(e) => setSearch(e.target.value)}
        placeholder="Search everything" aria-label="Search everything" className="search" />
      {allTags.length > 0 && (
        <div className="tag-filter" aria-label="Filter by tag">
          {allTags.map((t) => (
            <button key={t} type="button" className={picked.includes(t) ? "tag active" : "tag"}
              aria-pressed={picked.includes(t)} onClick={() => toggleTag(t)}>#{t}</button>
          ))}
        </div>
      )}
      {shown.length ? (
        <div className="grid two">{shown.map((n) => <NoteCard key={n.id} note={n} />)}</div>
      ) : <p className="empty">No notes found.</p>}
    </>
  );
}

function NotesOnly({ notes }: SectionProps) {
  const plain = notes.filter((n) => n.kind === "note");
  if (!plain.length) return <Empty what="note" />;
  return <div className="grid two">{plain.map((n) => <NoteCard key={n.id} note={n} />)}</div>;
}

function Ideas({ notes, reload }: SectionProps) {
  const [idea, setIdea] = useState("");
  const ideas = notes.filter((n) => n.kind === "idea");

  // quick add, so an idea can be saved without leaving the Dashboard
  async function add(e: FormEvent) {
    e.preventDefault();
    if (!idea.trim()) return;
    await api.addNote({ kind: "idea", title: idea.trim(), body: "", tags: "", steps: "", deadline: "", language: "" });
    setIdea("");
    reload();
  }

  return (
    <>
      <form onSubmit={add} className="row quick-add">
        <input type="text" value={idea} onChange={(e) => setIdea(e.target.value)}
          placeholder="Got an idea? Type it in one line" aria-label="New idea" />
        <button type="submit">Add idea</button>
      </form>
      {ideas.length ? (
        <div className="grid three">
          {ideas.map((n) => (
            <article key={n.id} className="card kind-idea">
              <Link to={noteLink(n.id)} className="card-title idea-title">{noteLabel(n)}</Link>
              {n.body && <small>{preview(n.body, 150)}</small>}
            </article>
          ))}
        </div>
      ) : <p className="empty">No ideas yet. Type one above.</p>}
    </>
  );
}

function Plans({ notes, replaceNote }: SectionProps) {
  // unfinished plans first, soonest deadline first
  const plans = useMemo(() => {
    const key = (n: Note) => {
      const { done, total } = planProgress(n);
      return `${total > 0 && done === total ? 1 : 0}${n.extra.deadline || "9999"}`;
    };
    return notes.filter((n) => n.kind === "plan").sort((a, b) => key(a).localeCompare(key(b)));
  }, [notes]);
  if (!plans.length) return <Empty what="plan" />;

  return (
    <div className="stack">
      {plans.map((n) => {
        const { done, total } = planProgress(n);
        const due = deadlineText(n);
        return (
          <article key={n.id} className="card kind-plan">
            <Link to={noteLink(n.id)} className="card-title">
              {noteLabel(n)}{total > 0 && done === total ? " ✅" : ""}
            </Link>
            {total > 0 && <Progress done={done} total={total} text={`${done}/${total} steps done`} />}
            {due && <small className={due.startsWith("overdue") ? "error" : undefined}>{due}</small>}
            {total > 0 && (
              <details>
                <summary>Steps</summary>
                <Steps note={n} onChange={replaceNote} />
              </details>
            )}
          </article>
        );
      })}
    </div>
  );
}

function CodeSnippets({ notes }: SectionProps) {
  const [language, setLanguage] = useState<string | null>(null);
  const snippets = notes.filter((n) => n.kind === "code");
  if (!snippets.length) return <Empty what="code snippet" />;

  const languages = [...new Set(snippets.map(codeLanguage))].sort();
  const shown = language ? snippets.filter((n) => codeLanguage(n) === language) : snippets;

  return (
    <>
      {languages.length > 1 && (
        <div className="tag-filter" aria-label="Language">
          {languages.map((l) => (
            <button key={l} type="button" className={l === language ? "tag active" : "tag"} aria-pressed={l === language}
              onClick={() => setLanguage(l === language ? null : l)}>{l}</button>
          ))}
        </div>
      )}
      <div className="stack">
        {shown.map((n) => (
          <details key={n.id} className="card kind-code">
            <summary>💻 {n.title} · {codeLanguage(n)}</summary>
            <CodeBlock code={n.body} />
            <Tags tags={n.tags} />
            <Link to={noteLink(n.id)}>Open</Link>
          </details>
        ))}
      </div>
    </>
  );
}
