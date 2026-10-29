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

export const preview = (text: string, length = 120) =>
  text.length > length ? text.slice(0, length) + "..." : text;

export function planProgress(note: Note) {
  const steps = note.extra.steps ?? [];
  return { done: steps.filter((s) => s.done).length, total: steps.length };
}

export function deadlineText(note: Note) {
  const deadline = note.extra.deadline;
  if (!deadline) return "";
  const due = new Date(deadline + "T00:00:00");
  if (Number.isNaN(due.getTime())) return `due ${deadline}`;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((due.getTime() - today.getTime()) / 86_400_000);
  if (days > 1) return `due in ${days} days`;
  if (days === 1) return "due tomorrow";
  if (days === 0) return "due today";
  return `overdue by ${-days} day${days < -1 ? "s" : ""}`;
}

export const codeLanguage = (note: Note) => note.extra.language ?? "other";
