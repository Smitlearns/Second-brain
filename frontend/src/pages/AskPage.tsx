import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import * as api from "../api";
import type { Chat, Message, Note } from "../api";
import { Markdown } from "../components/bits";

const SUGGESTIONS = [
  ["Summarize this note", "Summarize this note"],
  ["Quiz me", "Quiz me on this note with 3 questions"],
  ["Explain simply", "Explain this note simply"],
];

/** Chat with the AI about your notes. Each chat has its own address, /ask/<id>. */
export default function AskPage() {
  const chatId = Number(useParams().chatId) || null;
  const navigate = useNavigate();
  const [chats, setChats] = useState<Chat[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [focus, setFocus] = useState<Note | null>(null);
  const [question, setQuestion] = useState("");
  const [answering, setAnswering] = useState<number[]>([]); // chats waiting for an answer
  const busy = chatId !== null && answering.includes(chatId);
  const chatBox = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const openChat = useRef(chatId);
  openChat.current = chatId;

  // no chat picked: open the newest one, or start one
  useEffect(() => {
    if (chatId !== null) return;
    let cancelled = false; // React runs this twice in development; only the second one should make a chat
    api.getChats().then(async (list) => {
      if (cancelled) return;
      const id = list.length ? list[0].id : (await api.newChat()).id;
      navigate(`/ask/${id}`, { replace: true });
    });
    return () => {
      cancelled = true;
    };
  }, [chatId, navigate]);

  useEffect(() => {
    if (chatId === null) return;
    let cancelled = false; // a slow answer for the previous chat mustn't show up in this one
    api.getChats().then(setChats);
    api.getChat(chatId).then(
      (details) => {
        if (cancelled) return;
        setMessages(details.messages);
        setFocus(details.focus);
      },
      () => !cancelled && navigate("/ask", { replace: true }), // the chat was deleted
    );
    return () => {
      cancelled = true;
    };
  }, [chatId, navigate]);

  useEffect(() => {
    chatBox.current?.scrollTo({ top: chatBox.current.scrollHeight });
  }, [messages]);

  const renameChat = (id: number, title: string) =>
    setChats((list) => list.map((c) => (c.id === id ? { ...c, title } : c)));

  async function send(text: string) {
    text = text.trim();
    if (!text || busy || chatId === null) return;
    const id = chatId;
    setQuestion("");
    setAnswering((list) => [...list, id]);
    const replyKey = `reply-${Date.now()}`; // finds this reply again, even after other messages load
    const reply: Message = { role: "assistant", content: "Thinking...", sources: [], error: false, key: replyKey };
    setMessages((m) => [...m, { role: "user", content: text, sources: [], error: false }, reply]);
    const showReply = (changes: Partial<Message>) => {
      // if you opened another chat meanwhile, the server still saves the answer, just don't show it here
      if (openChat.current !== id) return;
      setMessages((m) => m.map((msg) => (msg.key === replyKey ? { ...msg, ...changes } : msg)));
    };

    try {
      const info = await api.ask(id, text, (content) => showReply({ content }));
      renameChat(id, info.title); // the first question names the chat in the list
      // the server has saved the answer by now, with its sources and whether the AI failed
      const saved = await api.getChat(id);
      if (openChat.current === id) setMessages(saved.messages);
      const last = saved.messages[saved.messages.length - 1];
      const failed = last?.role !== "assistant" || last.error;
      if (info.needsTitle && !failed) {
        // not awaited, so you can keep typing; if it fails the shortened question stays as the name
        api.makeChatTitle(id).then(({ title }) => renameChat(id, title), () => {});
      }
    } catch {
      showReply({ content: "Something went wrong sending your question. Try again.", error: true });
    } finally {
      setAnswering((list) => list.filter((c) => c !== id));
      if (openChat.current === id) input.current?.focus();
    }
  }

  async function startChat() {
    navigate(`/ask/${(await api.newChat()).id}`);
  }

  async function removeChat() {
    if (chatId === null || !confirm("Delete this chat?")) return;
    await api.deleteChat(chatId);
    navigate("/ask");
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    send(question);
  }

  return (
    <main className="wide">
      <div className="chat-layout">
        <aside className="chat-list">
          <button type="button" className="new-chat" onClick={startChat}>+ New chat</button>
          {chats.map((c) => (
            <Link key={c.id} to={`/ask/${c.id}`} className={c.id === chatId ? "active" : undefined}>{c.title}</Link>
          ))}
        </aside>

        <section className="chat-main">
          <div className="chat-top">
            <h1>Ask your brain</h1>
            <button type="button" className="secondary" onClick={removeChat}>Delete chat</button>
          </div>

          {focus && (
            <p className="focus">
              Talking about your note <Link to={`/dashboard/notes/${focus.id}`}><strong>{focus.title}</strong></Link>
            </p>
          )}

          <div id="chat" ref={chatBox}>
            {messages.map((m, i) => (
              <div key={m.id ?? m.key ?? `new-${i}`} className={`msg ${m.role === "user" ? "user" : "bot"}`}>
                {m.role === "assistant" ? <Markdown text={m.content} /> : m.content}
                {m.sources.length > 0 && <small>From your notes: {m.sources.join(", ")}</small>}
              </div>
            ))}
            {!messages.length && <p className="empty">Ask anything. Answers use the notes you saved.</p>}
          </div>

          {focus && (
            <div className="suggestions">
              {SUGGESTIONS.map(([label, text]) => (
                <button key={label} type="button" className="secondary" disabled={busy} onClick={() => send(text)}>
                  {label}
                </button>
              ))}
            </div>
          )}

          <form className="chat-form" onSubmit={submit}>
            <input ref={input} type="text" value={question} onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask your doubt..." aria-label="Your question" autoComplete="off" required autoFocus />
            <button type="submit" disabled={busy}>Send</button>
          </form>
        </section>
      </div>
    </main>
  );
}
