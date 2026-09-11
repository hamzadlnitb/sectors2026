"use client";

import { useEffect, useState } from "react";
import type { Step } from "@/lib/transcript";

export type RenderStep = Step & { tag?: string };

const FINDING_LABEL: Record<Step["finding"], string> = {
  confirmed: "confirmed",
  refuted: "refuted",
  inconclusive: "inconclusive",
};

/** Step-by-step replay with full transport controls — play/pause, rewind,
 *  forward, and jump-to-step (click a step number). At rest every step is
 *  visible (good first frame); the controls re-walk the agent's reasoning. */
export default function ReplayTimeline({ steps }: { steps: RenderStep[] }) {
  const n = steps.length;
  const [shown, setShown] = useState(n); // number of steps revealed (1..n)
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setShown((s) => (s >= n ? s : s + 1)), 850);
    return () => clearInterval(id);
  }, [playing, n]);

  useEffect(() => {
    if (shown >= n) setPlaying(false);
  }, [shown, n]);

  function togglePlay() {
    if (playing) {
      setPlaying(false);
    } else {
      if (shown >= n) setShown(0); // restart from the top
      setPlaying(true);
    }
  }
  const back = () => { setPlaying(false); setShown((s) => Math.max(1, s - 1)); };
  const forward = () => { setPlaying(false); setShown((s) => Math.min(n, s + 1)); };
  const jump = (step: number) => { setPlaying(false); setShown(step); };

  return (
    <>
      <div className="replay-bar">
        <button className="ctrl primary" onClick={togglePlay} aria-label={playing ? "Jeda" : "Putar"}>
          {playing ? <PauseIcon /> : <PlayIcon />} {playing ? "Jeda" : shown >= n ? "Putar ulang" : "Putar"}
        </button>
        <button className="ctrl" onClick={back} disabled={shown <= 1} aria-label="Mundur satu langkah">
          <BackIcon /> Mundur
        </button>
        <button className="ctrl" onClick={forward} disabled={shown >= n} aria-label="Maju satu langkah">
          Maju <FwdIcon />
        </button>
        <span className="step-count mono">langkah {Math.min(shown, n)} / {n}</span>
      </div>

      <div className="trail">
        {steps.map((s, i) => {
          const on = i < shown;
          const current = i + 1 === shown;
          return (
            <div
              key={s.step}
              className={`step${s.tag ? " moment-step" : ""}${current ? " current" : ""}`}
              style={{ opacity: on ? 1 : 0.2, filter: on ? "none" : "grayscale(0.55)" }}
            >
              <button
                className="gutter"
                onClick={() => jump(s.step)}
                aria-label={`Lompat ke langkah ${s.step}`}
                aria-current={current ? "step" : undefined}
              >
                {String(s.step).padStart(2, "0")}
              </button>
              <div className="sbody">
                <div className="step-head">
                  <span className="probe">{s.probe}</span>
                  <span className={`finding ${s.finding}`}>
                    <span className="fd" /> {FINDING_LABEL[s.finding]}
                  </span>
                  {s.tag && <span className="mtag">{s.tag}</span>}
                </div>
                <div className="step-reason">{s.reason}</div>
                <div className="step-foot">
                  <span className="cost">−{s.credits_spent} credits</span>
                  {s.budget_granted > 0 && <span className="grant">budget +{s.budget_granted} granted</span>}
                  <span className="rem">{s.credits_remaining} left</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

function PlayIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>;
}
function PauseIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>;
}
function BackIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M15 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
function FwdIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
