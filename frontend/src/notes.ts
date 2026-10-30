import type { Kind, Note, NoteFields } from "./api";

// Keep these in step with KINDS in app/database.py
// the icons are in components/icons.tsx
export const KINDS: Record<Kind, { label: string }> = {
  note: { label: "Note" },
  idea: { label: "Idea" },
  plan: { label: "Plan" },
};

export const KIND_LIST = Object.keys(KINDS) as Kind[];

export const TITLE_LABELS: Record<Kind, string> = {
  note: "Title",
  idea: "Your idea in one line",
  plan: "Goal, e.g. Finish the FastAPI course",
};

export const BODY_LABELS: Record<Kind, string> = {
  note: "Write your note...",
  idea: "Why it matters (optional)",
  plan: "Details (optional)",
};

export const emptyFields = (kind: Kind): NoteFields => ({
  kind, title: "", body: "", tags: "", steps: "", deadline: "",
});

/** The form fields for editing an existing note. */
export const fieldsFrom = (note: Note): NoteFields => ({
  kind: note.kind,
  title: note.title,
  body: note.body,
  tags: note.tags.join(", "),
  steps: (note.extra.steps ?? []).map((s) => s.text).join("\n"),
  deadline: note.extra.deadline ?? "",
});

/** Markdown without its symbols, for short previews: "**Big** [idea](url)" becomes "Big idea". */
export function plainText(text: string) {
  return text
    .replace(/```\w*/g, "")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+/gm, "")
    .replace(/(\*\*|\*|~~|`)(\S(?:.*?\S)?)\1/g, "$2")
    // _ only marks emphasis around whole words, so snake_case_names stay as they are
    .replace(/(^|\W)(__|_)(\S(?:.*?\S)?)\2(?=\W|$)/g, "$1$3");
}

export const preview = (text: string, length = 120) => {
  text = plainText(text);
  return text.length > length ? text.slice(0, length) + "..." : text;
};

export function planProgress(note: Note) {
  const steps = note.extra.steps ?? [];
  return { done: steps.filter((s) => s.done).length, total: steps.length };
}

export function planFinished(note: Note) {
  const { done, total } = planProgress(note);
  return total > 0 && done === total;
}

/** Days until the deadline (negative once it's passed), or null if there's no valid deadline. */
export function daysLeft(note: Note) {
  const due = parseDay(note.extra.deadline);
  if (!due) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - today.getTime()) / 86_400_000);
}

export const DUE_SOON_DAYS = 3;

/** Unfinished plans that are overdue or due within DUE_SOON_DAYS, soonest first. */
export function duePlans(notes: Note[]) {
  return notes
    .filter((n) => n.kind === "plan" && !planFinished(n))
    .map((n) => ({ note: n, days: daysLeft(n) }))
    .filter((p): p is { note: Note; days: number } => p.days !== null && p.days <= DUE_SOON_DAYS)
    .sort((a, b) => a.days - b.days)
    .map((p) => p.note);
}

/** "Today", "Yesterday" or "28 Oct", for lists. Saved times come from SQLite in UTC. */
export function shortDate(stamp: string) {
  const date = new Date(stamp.replace(" ", "T") + "Z");
  if (Number.isNaN(date.getTime())) return stamp;
  const days = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: sameYear ? undefined : "numeric" });
}

/** "28 Oct 2026, 13:21", for a single note. */
export function fullDate(stamp: string) {
  const date = new Date(stamp.replace(" ", "T") + "Z");
  return Number.isNaN(date.getTime()) ? stamp : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** A YYYY-MM-DD deadline as "2 Oct 2026". */
export function dayText(day: string) {
  const date = parseDay(day);
  return date ? date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : day;
}

/** A YYYY-MM-DD day as local midnight, or null if it isn't a date. */
function parseDay(day: string | undefined) {
  if (!day) return null;
  const date = new Date(day + "T00:00:00");
  return Number.isNaN(date.getTime()) ? null : date;
}

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

export function deadlineText(note: Note) {
  const deadline = note.extra.deadline;
  if (!deadline || planFinished(note)) return ""; // a finished plan isn't late
  const days = daysLeft(note);
  if (days === null) return `due ${dayText(deadline)}`;
  if (days > 1) return `due in ${days} days`;
  if (days === 1) return "due tomorrow";
  if (days === 0) return "due today";
  return `overdue by ${-days} day${days < -1 ? "s" : ""}`;
}

