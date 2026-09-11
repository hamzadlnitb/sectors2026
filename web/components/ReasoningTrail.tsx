"use client";

import { useRef, useState, type CSSProperties } from "react";

/** The landing's "proof" card: it doesn't just claim the agent shows its
 *  reasoning — it replays a real trail (plan → steps → verdict). */
export default function ReasoningTrail() {
  const total = 6; // 5 trail lines + verdict line
  const [revealed, setRevealed] = useState(total); // at rest: all visible
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  function replay() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (timer.current) clearInterval(timer.current);
    setRevealed(0);
    let n = 0;
    timer.current = setInterval(() => {
      n += 1;
      setRevealed(n);
      if (n >= total && timer.current) clearInterval(timer.current);
    }, 130);
  }

  const style = (i: number): CSSProperties =>
    i < revealed
      ? { opacity: 1, transform: "none" }
      : { opacity: 0, transform: "translateY(4px)" };

  return (
    <div className="terminal">
      <div className="term-head">
        <span className="dots">
          <i /><i /><i />
        </span>
        <span className="term-title mono">
          pantau · menyelidiki <b>FIXC</b>
        </span>
        <span className="term-live mono">memindai</span>
      </div>
      <div className="term-body">
        <div className="tl" style={style(0)}>
          <span className="p">›</span> <span className="lbl">rencana disusun</span> — 3 hipotesis · pagu 8 kredit
        </div>
        <div className="tl" style={style(1)}>
          <span className="p">›</span> <span className="lbl">langkah 1</span> volume_anomaly <span className="ok">6,2σ ✓</span>
        </div>
        <div className="tl" style={style(2)}>
          <span className="p">›</span> <span className="lbl">langkah 2</span> free_float <span className="ok">4% ✓</span>{" "}
          <span className="tag flag">⤴ eskalasi +7 kredit</span>
        </div>
        <div className="tl" style={style(3)}>
          <span className="p">›</span> <span className="lbl">langkah 3</span> structural <span className="ok">2× rights issue ✓</span>{" "}
          <span className="tag route">⟿ di luar rencana</span>
        </div>
        <div className="tl" style={style(4)}>
          <span className="p">›</span> <span className="lbl">langkah 4</span> foreign_flow <span className="ok">−Rp 47 M ✓</span>{" "}
          <span className="tag stop">■ bukti cukup</span>
        </div>
        <div className="verdict-line" style={style(5)}>
          <span className="score">87</span>
          <span className="bd" />
          <span className="bl">HIGH ALERT</span>
          <span className="conf">keyakinan 60% · hemat 43%</span>
        </div>
      </div>
      <div className="term-foot">
        <button type="button" onClick={replay}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M8 5v14l11-7z" />
          </svg>{" "}
          Putar ulang penalaran
        </button>
      </div>
    </div>
  );
}
