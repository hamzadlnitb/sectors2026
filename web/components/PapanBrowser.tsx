"use client";

import Link from "next/link";
import { useState } from "react";
import { bandMeta, type Band } from "@/lib/bands";
import type { Candidate } from "@/lib/watchlist";

export type PapanRun = {
  date: string; // "2026-09-14"
  time: string; // "16:27 UTC"
  credits: number | null;
  candidateCount: number;
  candidates: Candidate[];
  runLog: string[];
};

export type InvRef = { id: string; band: Band; score: number };

const SIG: Record<string, string> = {
  normal: "var(--sig-normal)",
  watch: "var(--sig-watch)",
  alert: "var(--sig-alert)",
  high: "var(--sig-danger)",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
function fmtLong(d: string) {
  const [y, m, day] = d.split("-").map(Number);
  return `${day} ${MONTHS[(m || 1) - 1]} ${y}`;
}
function fmtShort(d: string) {
  const [, m, day] = d.split("-").map(Number);
  return `${day} ${MONTHS[(m || 1) - 1]}`;
}

export default function PapanBrowser({
  runs,
  invBySymbol,
  repoUrl,
}: {
  runs: PapanRun[];
  invBySymbol: Record<string, InvRef>;
  repoUrl: string;
}) {
  const [selected, setSelected] = useState(runs[0]?.date ?? "");
  const run = runs.find((r) => r.date === selected) ?? runs[0];
  if (!run) return null;

  return (
    <>
      <div className="date-radios" role="radiogroup" aria-label="Pilih tanggal arsip">
        {runs.map((r) => (
          <label key={r.date} className={`dr${selected === r.date ? " on" : ""}`}>
            <input
              type="radio"
              name="papan-date"
              checked={selected === r.date}
              onChange={() => setSelected(r.date)}
            />
            <span className="d">{fmtShort(r.date)}</span>
            <span className="c mono">{r.candidateCount}</span>
          </label>
        ))}
      </div>

      {/* autonomy proof */}
      <div className="run-proof">
        <div className="rp-head">
          <span className="dots"><i /><i /><i /></span>
          <span className="rp-title mono">cron · <b>pantau-bot</b> · sapuan Tier-1 {fmtLong(run.date)}</span>
          <span className="rp-meta mono">{run.time} · {run.credits ?? 0} kredit</span>
        </div>
        <pre className="rp-log mono">{run.runLog.length ? run.runLog.join("\n") : "(log tidak tersedia)"}</pre>
        <div className="rp-links">
          <a href={`${repoUrl}/blob/main/runs/${run.date}/run.log`} target="_blank" rel="noopener noreferrer">
            run.log di GitHub →
          </a>
          <a href={`${repoUrl}/commits/main/runs/${run.date}`} target="_blank" rel="noopener noreferrer">
            commit pantau-bot →
          </a>
          <a href={`${repoUrl}/actions`} target="_blank" rel="noopener noreferrer">
            GitHub Actions →
          </a>
        </div>
      </div>

      {/* candidate list */}
      <div className="run-list">
        {run.candidates.map((c, i) => {
          const inv = invBySymbol[c.symbol];
          const band = inv ? bandMeta(inv.band) : null;
          const color = band ? SIG[band.cls] : undefined;
          return (
            <div className="cand" key={c.symbol}>
              <span className="rank">{i + 1}</span>
              <div className="main">
                {inv ? (
                  <Link href={`/investigasi/${inv.id}`} className="sym">{c.symbol}</Link>
                ) : (
                  <span className="sym">{c.symbol}</span>
                )}
                <div className="why">{c.alasan}</div>
              </div>
              <div className="right">
                {inv && band && color ? (
                  <Link
                    href={`/investigasi/${inv.id}`}
                    className="sel"
                    style={{ color, background: `color-mix(in srgb, ${color} 13%, transparent)` }}
                  >
                    <span className="bd" style={{ background: color }} /> {band.label} · {inv.score}
                  </Link>
                ) : (
                  <span className="sel pending">belum diselidiki</span>
                )}
                <div className="sscore">
                  {c.score.toFixed(2)}
                  <div className="bar"><i style={{ width: `${Math.min(100, Math.round(c.score * 100))}%` }} /></div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
