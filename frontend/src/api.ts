// Everything the React app asks the server for. /flask/... is the Flask app, /api/... is FastAPI.

export type Kind = "note" | "idea" | "plan";

export interface Step {
  text: string;
  done: boolean;
}

export interface Note {
  id: number;
  title: string;
  body: string;
  tags: string[];
  kind: Kind;
  pinned: boolean;
  created_at: string;
  extra: { steps?: Step[]; deadline?: string };
}

/** What the note forms send. Plan steps are one per line, tags are comma separated. */
export interface NoteFields {
  kind: Kind;
  title: string;
  body: string;
  tags: string;
  steps: string;
  deadline: string;
}

export interface Stats {
  notes: number;
  this_week: number;
  pinned: number;
  chats: number;
  questions: number;
}

export interface Link {
  from: number;
  to: number;
  how: string;
}

export interface Chat {
  id: number;
  title: string;
  note_id: number | null;
  auto_titled: number;
  created_at: string;
}

export interface Message {
  id?: number;
  role: "user" | "assistant";
  content: string;
  sources: string[];
  error: boolean;
  key?: string; // only on a reply still being written, before the server gives it an id
}

export interface ChatDetails {
  chat: Chat;
  messages: Message[];
  focus: Note | null;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    // FastAPI puts the reason in "detail", Flask in "error"
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail ?? data.error ?? `Request failed (${response.status})`);
  }
  return response.json();
}

function sendJson<T>(method: string, url: string, body?: unknown): Promise<T> {
  return request<T>(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

// ---------- Flask: the Notes page ----------

export const addNote = (fields: NoteFields) => sendJson<{ id: number }>("POST", "/flask/notes", fields);

export function importFiles(files: FileList) {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  return request<{ imported: number; problems: string[] }>("/flask/import", { method: "POST", body: form });
}

export const EXPORT_URL = "/flask/export";

// ---------- FastAPI: notes ----------

export const getNotes = () => request<Note[]>("/api/notes");
export const searchNotes = (q: string) => request<Note[]>(`/api/notes/search?q=${encodeURIComponent(q)}`);
export const getNote = (id: number) => request<Note>(`/api/notes/${id}`);
export const updateNote = (id: number, fields: NoteFields) => sendJson<Note>("PUT", `/api/notes/${id}`, fields);
export const deleteNote = (id: number) => sendJson<unknown>("DELETE", `/api/notes/${id}`);
export const setPinned = (id: number, pinned: boolean) => sendJson<Note>("PUT", `/api/notes/${id}/pinned`, { pinned });
export const setStepDone = (id: number, index: number, done: boolean) =>
  sendJson<Note>("PUT", `/api/notes/${id}/steps/${index}`, { done });
export const getRelated = (id: number) => request<Note[]>(`/api/notes/${id}/related`);
export const getTags = () => request<string[]>("/api/tags");
export const getStats = () => request<Stats>("/api/stats");
export const getLinks = () => request<Link[]>("/api/graph");

// ---------- FastAPI: chats ----------

export const getChats = () => request<Chat[]>("/api/chats");
export const newChat = () => sendJson<{ id: number }>("POST", "/api/chats");
export const chatAboutNote = (noteId: number) => sendJson<{ id: number }>("POST", `/api/chats/about/${noteId}`);
export const getChat = (id: number) => request<ChatDetails>(`/api/chats/${id}`);
export const deleteChat = (id: number) => sendJson<unknown>("DELETE", `/api/chats/${id}`);
export const makeChatTitle = (id: number) => sendJson<{ title: string }>("POST", `/api/chats/${id}/title`);

export interface AnswerInfo {
  title: string;
  needsTitle: boolean;
}

/** Ask a question. onText gets the answer so far, a few words at a time, as the AI writes it. */
export async function ask(chatId: number, question: string, onText: (text: string) => void): Promise<AnswerInfo> {
  const response = await fetch(`/api/chats/${chatId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!response.ok || !response.body) throw new Error(`Request failed (${response.status})`);

  // headers must be plain ASCII, so the server URL-encodes them
  const info: AnswerInfo = {
    title: decodeURIComponent(response.headers.get("X-Chat-Title") ?? ""),
    needsTitle: response.headers.get("X-Needs-Title") === "1",
  };

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let text = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    text += decoder.decode(value, { stream: true });
    onText(text);
  }
  return info;
}
