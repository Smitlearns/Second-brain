import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataSet } from "vis-data";
import { Network } from "vis-network";
import { getLinks, type Kind, type Link, type Note } from "../api";
import { KIND_LIST } from "../notes";
import { themeColor, useTheme } from "../theme";
import { noteLink } from "./bits";

// the same colours as the type icons in style.css
const KIND_COLORS: Record<Kind, string> = { note: "blue", idea: "yellow", plan: "green", code: "purple" };

/** How notes connect: lines for shared tags, dashed lines for similar content. Click a note to open it. */
export default function Graph({ notes }: { notes: Note[] }) {
  const box = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const [links, setLinks] = useState<Link[] | null>(null);
  const [failed, setFailed] = useState(false);
  const theme = useTheme(); // redraw in the new colours when the theme changes

  useEffect(() => {
    getLinks().then(setLinks, () => setFailed(true));
  }, []);

  useEffect(() => {
    if (!box.current || !links) return;
    const colors = Object.fromEntries(KIND_LIST.map((k) => [k, themeColor(KIND_COLORS[k])])) as Record<Kind, string>;
    const nodes = new DataSet(notes.map((n) => ({
      id: n.id,
      label: n.title.slice(0, 30),
      title: `${n.title}\n${n.tags.map((t) => "#" + t).join(", ")}`,
      color: colors[n.kind],
      size: n.pinned ? 22 : 14,
    })));
    const edges = new DataSet(links.map((l, i) => ({
      id: i, from: l.from, to: l.to, title: l.how, dashes: l.how.startsWith("similar"),
    })));
    const network = new Network(box.current, { nodes, edges }, {
      nodes: { shape: "dot", font: { color: themeColor("text"), size: 13 } },
      edges: { color: { color: themeColor("edge"), highlight: themeColor("accent") }, smooth: false },
      physics: { stabilization: { iterations: 200 } },
    });
    network.on("doubleClick", ({ nodes: picked }) => {
      if (picked.length) navigate(noteLink(picked[0]));
    });
    return () => network.destroy();
  }, [notes, links, navigate, theme]);

  if (notes.length < 2) return <p className="empty">Save a few notes to see how they connect.</p>;
  if (failed) return <p className="error">Couldn't load the connections. Try again.</p>;

  return (
    <>
      <small>
        {links ? `${links.length} connections. ` : "Finding connections... "}
        Solid lines share a tag, dashed lines mean similar content. Drag notes around, scroll to zoom, hover for
        details, double-click to open. Blue is a note, yellow an idea, green a plan, purple code. Pinned notes are bigger.
      </small>
      <div ref={box} className="graph" />
    </>
  );
}
