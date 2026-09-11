"use client";

import { useRef } from "react";
import type { EvidenceEntry } from "@/lib/transcript";
import { fmtAsOf, fmtParams } from "@/lib/format";

type Node = string | { id: string; label: string };

/** Wrap the first occurrence of each evidence `display` value in the narrative
 *  as a clickable citation. A leading minus (e.g. "−Rp 47 M") is also matched
 *  without it, since prose often drops the sign. */
function buildNodes(text: string, evidence: EvidenceEntry[]): Node[] {
  const cands: { id: string; text: string }[] = [];
  for (const e of evidence) {
    if (!e.display) continue;
    cands.push({ id: e.id, text: e.display });
    const noMinus = e.display.replace(/^[-−]\s*/, "");
    if (noMinus !== e.display) cands.push({ id: e.id, text: noMinus });
  }
  cands.sort((a, b) => b.text.length - a.text.length);

  const used = new Set<string>();
  const nodes: Node[] = [];
  let buffer = "";
  let i = 0;
  while (i < text.length) {
    const hit = cands.find((c) => !used.has(c.id) && c.text && text.startsWith(c.text, i));
    if (hit) {
      if (buffer) { nodes.push(buffer); buffer = ""; }
      nodes.push({ id: hit.id, label: hit.text });
      used.add(hit.id);
      i += hit.text.length;
    } else {
      buffer += text[i];
      i += 1;
    }
  }
  if (buffer) nodes.push(buffer);
  return nodes;
}

export default function EvidenceVerdict({
  evidence,
  narrative,
  narrativeSource,
}: {
  evidence: EvidenceEntry[];
  narrative: string;
  narrativeSource: "llm" | "template";
}) {
  const refs = useRef<Record<string, HTMLDetailsElement | null>>({});

  function openEvidence(id: string) {
    const el = refs.current[id];
    if (!el) return;
    el.open = true;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.remove("flash");
    void el.offsetWidth; // reflow so the animation replays
    el.classList.add("flash");
  }

  const nodes = buildNodes(narrative, evidence);

  return (
    <>
      <section>
        <div className="sec-label">
          <h2>Evidence ledger</h2>
          <span className="n">// {evidence.length} entries · each traceable</span>
        </div>
        <div className="ev-list">
          {evidence.map((e) => (
            <details key={e.id} id={`ev-${e.id}`} className="ev" ref={(el) => { refs.current[e.id] = el; }}>
              <summary>
                <div className="em">
                  <div className="el">{e.label}</div>
                  <div className="evv">{e.display}</div>
                  <div className="emeta">
                    <span className="p">{e.probe}</span>
                    <span className="c">{e.credits_spent} credits</span>
                  </div>
                </div>
                <span className="chev">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              </summary>
              <div className="src">
                <div className="row"><span className="sk">endpoint</span><span className="sv">{e.source_endpoint} <span className="tp">· {e.source_transport}</span></span></div>
                <div className="row"><span className="sk">params</span><span className="sv">{fmtParams(e.source_params)}</span></div>
                <div className="row"><span className="sk">as_of</span><span className="sv">{fmtAsOf(e.as_of)}</span></div>
              </div>
            </details>
          ))}
        </div>
      </section>

      <section>
        <div className="sec-label">
          <h2>Verdict</h2>
          <span className="n">// adjudicator</span>
        </div>
        <div className="panel narr">
          {narrativeSource === "llm" ? (
            <span className="srcbadge llm">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>{" "}
              LLM narrative · passed citation validator
            </span>
          ) : (
            <span className="srcbadge tmpl">
              ⚑ Template deterministik · validator menolak keluaran LLM
            </span>
          )}
          <p>
            {nodes.map((n, i) =>
              typeof n === "string" ? (
                <span key={i}>{n}</span>
              ) : (
                <button key={i} className="cite" onClick={() => openEvidence(n.id)}>
                  {n.label}
                </button>
              )
            )}
          </p>
        </div>
      </section>
    </>
  );
}
