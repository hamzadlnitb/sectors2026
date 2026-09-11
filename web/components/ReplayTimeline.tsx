"use client";

import { useRef, useState } from "react";
import type { Step } from "@/lib/transcript";

export type RenderStep = Step & { tag?: string };

const FINDING_LABEL: Record<Step["finding"], string> = {
  confirmed: "confirmed",
  refuted: "refuted",
  inconclusive: "inconclusive",
};

/** Step-by-step replay — reveals the agent's reasoning in order, not just the
 *  final result. At rest every step is visible (good first frame); Replay
 *  re-reveals them, Step advances one at a time. */
export default function ReplayTimeline({ steps }: { steps: RenderStep[] }) {
  const [shown, setShown] = useState(steps.length);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  function play() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (timer.current) clearInterval(timer.current);
    setShown(0);
    let n = 0;
    timer.current = setInterval(() => {
      n += 1;
      setShown(n);
      if (n >= steps.length && timer.current) clearInterval(timer.current);
    }, 720);
  }

  function stepOnce() {
    if (timer.current) clearInterval(timer.current);
    setShown((s) => (s >= steps.length ? 1 : s + 1));
  }

  return (
    <>
      <div className="replay-bar">
        <button className="ctrl primary" onClick={play}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M8 5v14l11-7z" />
          </svg>{" "}
          Replay
        </button>
        <button className="ctrl" onClick={stepOnce}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>{" "}
          Step
        </button>
        <span className="step-count mono">
          {Math.min(shown, steps.length)} / {steps.length} steps
        </span>
      </div>

      <div className="trail">
        {steps.map((s, i) => {
          const on = i < shown;
          return (
            <div
              key={s.step}
              className={`step${s.tag ? " moment-step" : ""}`}
              style={{ opacity: on ? 1 : 0.2, filter: on ? "none" : "grayscale(0.55)" }}
            >
              <div className="gutter">{String(s.step).padStart(2, "0")}</div>
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
