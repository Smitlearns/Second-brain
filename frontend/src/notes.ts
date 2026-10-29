import type { Kind, Note, NoteFields } from "./api";

// Keep these in step with KINDS and LANGUAGES in app/database.py
export const KINDS: Record<Kind, { icon: string; label: string }> = {
  note: { icon: "📝", label: "Note" },
  idea: { icon: "💡", label: "Idea" },
  plan: { icon: "🗺️", label: "Plan" },
  code: { icon: "💻", label: "Code" },
};

export const KIND_LIST = Object.keys(KINDS) as Kind[];

export const LANGUAGES = [
  "python", "javascript", "typescript", "html", "css", "sql", "bash", "java", "c", "cpp", "other",
];

export const TITLE_LABELS: Record<Kind, string> = {
  note: "Title",
  idea: "Your idea in one line",
  plan: "Goal, e.g. Finish the FastAPI course",
  code: "What does this code do?",
};

export const BODY_LABELS: Record<Kind, string> = {
  note: "Write your note...",
  idea: "Why it matters (optional)",
  plan: "Details (optional)",
  code: "Paste your code...",
};

export const emptyFields = (kind: Kind): NoteFields => ({
  kind, title: "", body: "", tags: "", steps: "", deadline: "", language: "python",
});

/** The form fields for editing an existing note. */
export const fieldsFrom = (note: Note): NoteFields => ({
  kind: note.kind,
  title: note.title,
  body: note.body,
  tags: note.tags.join(", "),
  steps: (note.extra.steps ?? []).map((s) => s.text).join("\n"),
  deadline: note.extra.deadline ?? "",
  language: note.extra.language ?? "other",
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
  const deadline = note.extra.deadline;
  if (!deadline) return null;
  const due = new Date(deadline + "T00:00:00");
  if (Number.isNaN(due.getTime())) return null;
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

export function deadlineText(note: Note) {
  const deadline = note.extra.deadline;
  if (!deadline) return "";
  const days = daysLeft(note);
  if (days === null) return `due ${deadline}`;
  if (days > 1) return `due in ${days} days`;
  if (days === 1) return "due tomorrow";
  if (days === 0) return "due today";
  return `overdue by ${-days} day${days < -1 ? "s" : ""}`;
}

export const codeLanguage = (note: Note) => note.extra.language ?? "other";
