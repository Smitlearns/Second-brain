import { CodeXml, FileText, Lightbulb, Map as MapIcon, Pin, type LucideIcon } from "lucide-react";
import type { Kind, Note } from "../api";

export const KIND_ICONS: Record<Kind, LucideIcon> = { note: FileText, idea: Lightbulb, plan: MapIcon, code: CodeXml };

/** The type of a note as a small tile in its colour: blue note, yellow idea, green plan, purple code. */
export function KindIcon({ kind, size = 15 }: { kind: Kind; size?: number }) {
  const Icon = KIND_ICONS[kind];
  return <span className={`kind-icon k-${kind}`}><Icon size={size} aria-hidden /></span>;
}

/** A note's title with its type icon, and a pin if it's pinned. */
export function NoteLabel({ note }: { note: Note }) {
  return (
    <span className="note-label">
      <KindIcon kind={note.kind} />
      <span>{note.title}</span>
      {note.pinned && <Pin size={14} className="pinned" aria-label="Pinned" />}
    </span>
  );
}
