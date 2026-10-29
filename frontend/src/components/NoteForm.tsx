import { useState, type FormEvent } from "react";
import type { NoteFields } from "../api";
import { BODY_LABELS, LANGUAGES, TITLE_LABELS } from "../notes";

interface Props {
  fields: NoteFields;
  onChange: (fields: NoteFields) => void;
  onSubmit: () => Promise<void>;
  submitLabel: string;
  onCancel?: () => void;
}

/** The fields for one type of note. Used on the Notes page and when editing a note. */
export default function NoteForm({ fields, onChange, onSubmit, submitLabel, onCancel }: Props) {
  const [saving, setSaving] = useState(false);
  const { kind } = fields;
  const set = (name: keyof NoteFields) => (e: { target: { value: string } }) =>
    onChange({ ...fields, [name]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit();
    } finally {
      setSaving(false);
    }
  }

  const title = (
    <input type="text" value={fields.title} onChange={set("title")} placeholder={TITLE_LABELS[kind]}
      aria-label={TITLE_LABELS[kind]} className={kind === "idea" ? "big" : undefined} required />
  );
  // ideas and plans can be saved without a body, notes and code can't
  const bodyRequired = kind === "note" || kind === "code";

  return (
    <form onSubmit={submit} className={`card form-${kind}`}>
      {kind === "code" ? (
        <div className="row">
          {title}
          <select value={fields.language} onChange={set("language")} aria-label="Language">
            {LANGUAGES.map((lang) => <option key={lang} value={lang}>{lang}</option>)}
          </select>
        </div>
      ) : title}

      {kind === "plan" && (
        <>
          <label className="field">Steps, one per line
            <textarea value={fields.steps} onChange={set("steps")} rows={5}
              placeholder={"Watch lessons 1-5\nBuild the notes app\nDeploy it"} />
          </label>
          <label className="field">Deadline (optional)
            <input type="date" value={fields.deadline} onChange={set("deadline")} />
          </label>
        </>
      )}

      <textarea value={fields.body} onChange={set("body")} placeholder={BODY_LABELS[kind]} aria-label={BODY_LABELS[kind]}
        rows={{ note: 6, idea: 3, plan: 2, code: 10 }[kind]} className={kind === "code" ? "code" : undefined}
        spellCheck={kind !== "code"} required={bodyRequired} />
      <input type="text" value={fields.tags} onChange={set("tags")} placeholder="Tags, separated by commas (optional)"
        aria-label="Tags" />

      <div className="buttons">
        <button type="submit" disabled={saving}>{saving ? "Saving..." : submitLabel}</button>
        {onCancel && <button type="button" className="secondary" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}
