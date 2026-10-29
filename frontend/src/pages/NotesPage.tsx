import { useState, type FormEvent } from "react";
import { Download, Upload } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { addNote, EXPORT_URL, importFiles, type Kind } from "../api";
import { KIND_ICONS } from "../components/icons";
import NoteForm from "../components/NoteForm";
import { emptyFields, KIND_LIST, KINDS } from "../notes";

const SAVE_LABELS: Record<Kind, string> = { note: "Save note", idea: "Save idea", plan: "Save plan", code: "Save snippet" };

/** Add notes of each type, import files and download everything. Saving goes to Flask. */
export default function NotesPage() {
  const [params, setParams] = useSearchParams();
  const kind = KIND_LIST.find((k) => k === params.get("kind")) ?? "note";
  const [fields, setFields] = useState(() => emptyFields(kind));
  const [message, setMessage] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [importing, setImporting] = useState(false);

  function pickKind(next: Kind) {
    setParams(next === "note" ? {} : { kind: next }, { replace: true });
    // keep what was typed, so switching type by mistake doesn't lose it
    setFields({ ...fields, kind: next });
  }

  async function save() {
    setMessage("");
    setProblems([]);
    try {
      // the type comes from the address, which can change without pickKind (nav link, back button)
      await addNote({ ...fields, kind });
      // stay on the same type, so saving several ideas in a row is quick
      setFields(emptyFields(kind));
      setMessage("Saved.");
    } catch (e) {
      setProblems([(e as Error).message]);
    }
  }

  async function importAll(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const input = e.currentTarget.elements.namedItem("files") as HTMLInputElement;
    if (!input.files?.length) return;
    setMessage("");
    setImporting(true);
    try {
      const result = await importFiles(input.files);
      setMessage(`Imported ${result.imported} note${result.imported === 1 ? "" : "s"}.`);
      setProblems(result.problems);
      input.value = "";
    } catch (err) {
      setProblems([(err as Error).message]);
    } finally {
      setImporting(false);
    }
  }

  return (
    <main>
      <header className="page-head">
        <div>
          <p className="eyebrow">Capture</p>
          <h1>New note</h1>
        </div>
      </header>

      {message && <p className="saved">{message} <Link to="/dashboard">See it in the Dashboard</Link></p>}
      {problems.map((p) => <p key={p} className="error">{p}</p>)}

      <div className="pills" role="tablist" aria-label="Type of note">
        {KIND_LIST.map((k) => {
          const Icon = KIND_ICONS[k];
          return (
            <button key={k} type="button" role="tab" aria-selected={k === kind}
              className={k === kind ? "pill active" : "pill"} onClick={() => pickKind(k)}>
              <Icon size={15} /> {KINDS[k].label}
            </button>
          );
        })}
      </div>

      <NoteForm fields={{ ...fields, kind }} onChange={setFields} onSubmit={save} submitLabel={SAVE_LABELS[kind]} />

      <form onSubmit={importAll} className="card">
        <strong className="with-icon"><Upload size={16} /> Import files</strong>
        <small>.txt, .md or .pdf. Long files are split into several notes. Markdown is split at each
          "# Heading", so a file from "Download all notes" imports back.</small>
        <input type="file" name="files" accept=".txt,.md,.pdf" multiple required />
        <div className="buttons">
          <button type="submit" disabled={importing}>{importing ? "Importing..." : "Import"}</button>
        </div>
      </form>

      <a href={EXPORT_URL} className="with-icon"><Download size={16} /> Download all notes as Markdown</a>
    </main>
  );
}
