"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { bandMeta, type Band } from "@/lib/bands";
import { isWeekend, weekdayId } from "@/lib/format";
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

const FULL_MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
const DOW = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];
const pad = (n: number) => String(n).padStart(2, "0");
function fmtLong(d: string) {
  const [y, m, day] = d.split("-").map(Number);
  return `${weekdayId(d)}, ${day} ${FULL_MONTHS[(m || 1) - 1]} ${y}`;
}

export default function PapanBrowser({
  runs,
  invBySymbol,
}: {
  runs: PapanRun[];
  invBySymbol: Record<string, InvRef>;
}) {
  const [selected, setSelected] = useState(runs[0]?.date ?? "");
  const initParts = (runs[0]?.date ?? "2026-01-01").split("-").map(Number);
  const [view, setView] = useState({ y: initParts[0], m: initParts[1] });
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  const run = runs.find((r) => r.date === selected) ?? runs[0];
  if (!run) return null;

  const runByDate = new Map(runs.map((r) => [r.date, r]));
  const startDow = (new Date(Date.UTC(view.y, view.m - 1, 1)).getUTCDay() + 6) % 7; // Mon=0
  const daysInMonth = new Date(Date.UTC(view.y, view.m, 0)).getUTCDate();
  const cells: (number | null)[] = [];
  for (let i = 0; i < startDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  const prevMonth = () => setView((v) => (v.m === 1 ? { y: v.y - 1, m: 12 } : { y: v.y, m: v.m - 1 }));
  const nextMonth = () => setView((v) => (v.m === 12 ? { y: v.y + 1, m: 1 } : { y: v.y, m: v.m + 1 }));

  return (
    <>
      <div className="papan-top">
        <div className="papan-intro">
          <span className="ic">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="txt">
            Tiap hari bursa, cron <b>17:30 WIB</b> menyapu sinyal Tier-1, menyusun watchlist kandidat, lalu agen
            menyelidiki yang paling mencurigakan — <b>tanpa ditunggui manusia</b>. Pilih tanggal untuk menelusuri
            arsipnya; tiap run ber-timestamp dan bisa diverifikasi ke commit <b>pantau-bot</b> di GitHub. Skor
            kandidat = skor <b>seleksi</b>, bukan skor PANTAU.
          </div>
        </div>
        <div className="datepick" ref={wrapRef}>
          <button className="dp-trigger" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="dialog">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <rect x="3.5" y="5" width="17" height="16" rx="2" /><path d="M3.5 9.5h17M8 3v4M16 3v4" strokeLinecap="round" />
            </svg>
            <span className="dp-date">{fmtLong(selected)}</span>
            <span className="dp-count mono">{run.candidateCount} kandidat</span>
            <svg className={`dp-chev${open ? " up" : ""}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          {open && (
            <div className="dp-pop" role="dialog" aria-label="Pilih tanggal">
              <div className="cal">
                <div className="cal-head">
                  <button className="cal-nav" onClick={prevMonth} aria-label="Bulan sebelumnya">‹</button>
                  <span className="cal-title mono">{FULL_MONTHS[view.m - 1]} {view.y}</span>
                  <button className="cal-nav" onClick={nextMonth} aria-label="Bulan berikutnya">›</button>
                </div>
                <div className="cal-grid">
                  {DOW.map((d) => <span className="cal-dow" key={d}>{d}</span>)}
                  {cells.map((day, i) => {
                    if (day === null) return <span className="cal-day empty" key={`e${i}`} />;
                    const ds = `${view.y}-${pad(view.m)}-${pad(day)}`;
                    const r = runByDate.get(ds);
                    if (!r) return <span className={`cal-day${isWeekend(ds) ? " weekend" : ""}`} key={ds}>{day}</span>;
                    return (
                      <button
                        key={ds}
                        className={`cal-day run${selected === ds ? " on" : ""}`}
                        onClick={() => { setSelected(ds); setOpen(false); }}
                        aria-pressed={selected === ds}
                        aria-label={`${day} ${FULL_MONTHS[view.m - 1]} — ${r.candidateCount} kandidat`}
                      >
                        {day}
                        <span className="pip" />
                      </button>
                    );
                  })}
                </div>
                <div className="cal-legend mono"><span className="pip" /> ada run · <span className="we-key">Sab/Min</span> bursa tutup</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* candidate list */}
      <div className="run-list" key={run.date}>
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
