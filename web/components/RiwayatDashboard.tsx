"use client";

import Link from "next/link";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Band } from "@/lib/bands";

export type RiwayatRun = {
  as_of: string;
  date: string; // label pendek "9 Sep"
  score: number;
  band: Band;
  cls: "normal" | "watch" | "alert" | "high";
  label: string; // NORMAL/WATCH/ALERT/HIGH ALERT
  cov: number;
  covTotal: number;
  conf: number; // %
  moments: string[];
  id: string;
};
export type RiwayatSeries = { symbol: string; runs: RiwayatRun[] };
export type RiwayatSummary = { total: number; symbols: number; flagged: number; avgCov: number };

const SIG: Record<string, string> = {
  normal: "var(--sig-normal)",
  watch: "var(--sig-watch)",
  alert: "var(--sig-alert)",
  high: "var(--sig-danger)",
};
const PALETTE = ["#35c5c9", "#58cc78", "#e6b13e", "#ec8b45", "#ec6a60", "#a78bfa", "#60a5fa", "#f472b6"];
const MOMENT: Record<string, string> = { adaptive: "adaptif", escalation: "eskalasi", memory: "memori" };

function OverviewTip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  const rows = [...payload].filter((p) => p.value != null).sort((a, b) => b.value - a.value);
  return (
    <div className="rw-tip">
      <div className="rw-tip-h">{label}</div>
      {rows.map((p) => (
        <div className="rw-tip-row" key={p.name}>
          <span className="rw-tip-dot" style={{ background: p.color }} /> {p.name}
          <b>{p.value}</b>
        </div>
      ))}
    </div>
  );
}

function SymTip({ active, payload }: { active?: boolean; payload?: { payload: RiwayatRun }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rw-tip">
      <div className="rw-tip-h">{r.date} 2026</div>
      <div className="rw-tip-row"><span className="rw-tip-dot" style={{ background: SIG[r.cls] }} /> skor <b style={{ color: SIG[r.cls] }}>{r.score}</b> · {r.label}</div>
      <div className="rw-tip-sub">{r.cov}/{r.covTotal} komponen · keyakinan {r.conf}%{r.cov <= 2 && r.score >= 60 ? " ⚠ cakupan tipis" : ""}</div>
    </div>
  );
}

function BandDot(props: { cx?: number; cy?: number; payload?: RiwayatRun }) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null || !payload) return <g />;
  return <circle cx={cx} cy={cy} r={4} fill={SIG[payload.cls]} stroke="var(--surface)" strokeWidth={1.5} />;
}

export default function RiwayatDashboard({ series, summary }: { series: RiwayatSeries[]; summary: RiwayatSummary }) {
  // Overview: pivot skor per tanggal, satu garis per emiten.
  const allDates = [...new Set(series.flatMap((s) => s.runs.map((r) => r.as_of)))].sort();
  const labelOf = new Map(series.flatMap((s) => s.runs.map((r) => [r.as_of, r.date] as const)));
  const overview = allDates.map((d) => {
    const row: Record<string, string | number> = { date: labelOf.get(d) ?? d };
    for (const s of series) {
      const r = s.runs.find((x) => x.as_of === d);
      if (r) row[s.symbol] = r.score;
    }
    return row;
  });

  return (
    <div className="rw-dash">
      {/* ringkasan */}
      <div className="rw-tiles">
        <Tile n={summary.total} k="investigasi" />
        <Tile n={summary.symbols} k="emiten dipantau" />
        <Tile n={summary.flagged} k="perlu perhatian" accent="var(--sig-alert)" />
        <Tile n={summary.avgCov.toFixed(1)} k="rata cakupan (dari 6)" />
      </div>

      {/* overview semua emiten */}
      <section className="rw-panel">
        <div className="rw-panel-h">
          <h2>Tren skor semua emiten</h2>
          <p>Tiap garis satu emiten. Naik = makin waspada. Arahkan kursor untuk detail.</p>
        </div>
        <div className="rw-chart-lg">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={overview} margin={{ top: 8, right: 14, bottom: 4, left: -18 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "var(--dim)", fontSize: 11 }} stroke="var(--border)" tickMargin={8} />
              <YAxis domain={[0, 100]} ticks={[0, 30, 60, 80, 100]} tick={{ fill: "var(--dim)", fontSize: 11 }} stroke="var(--border)" />
              <Tooltip content={<OverviewTip />} cursor={{ stroke: "var(--border-strong)" }} />
              {series.map((s, i) => (
                <Line key={s.symbol} type="monotone" dataKey={s.symbol} name={s.symbol} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot={{ r: 2.5 }} activeDot={{ r: 4.5 }} connectNulls={false} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="rw-legend">
          {series.map((s, i) => (
            <span className="rw-leg" key={s.symbol}><span className="rw-leg-d" style={{ background: PALETTE[i % PALETTE.length] }} /> {s.symbol}</span>
          ))}
        </div>
      </section>

      {/* per emiten */}
      <div className="rw-grid">
        {series.map((s) => (
          <section className="rw-card" key={s.symbol}>
            <div className="rw-head">
              <span className="rw-sym">{s.symbol}</span>
              <span className="rw-range">{s.runs.length} investigasi · {s.runs[0].date} – {s.runs[s.runs.length - 1].date}</span>
            </div>
            <div className="rw-chart-sm">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={s.runs} margin={{ top: 6, right: 10, bottom: 0, left: -22 }}>
                  <ReferenceArea y1={0} y2={30} fill="var(--sig-normal)" fillOpacity={0.05} />
                  <ReferenceArea y1={30} y2={60} fill="var(--sig-watch)" fillOpacity={0.05} />
                  <ReferenceArea y1={60} y2={80} fill="var(--sig-alert)" fillOpacity={0.06} />
                  <ReferenceArea y1={80} y2={100} fill="var(--sig-danger)" fillOpacity={0.07} />
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: "var(--dim)", fontSize: 10 }} stroke="var(--border)" tickMargin={6} />
                  <YAxis domain={[0, 100]} ticks={[0, 30, 60, 80, 100]} tick={{ fill: "var(--dim)", fontSize: 10 }} stroke="var(--border)" width={30} />
                  <Tooltip content={<SymTip />} cursor={{ stroke: "var(--border-strong)" }} />
                  <Line type="monotone" dataKey="score" stroke="var(--accent)" strokeWidth={2} dot={<BandDot />} activeDot={{ r: 5.5 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="rw-rows">
              {s.runs.map((r, i) => {
                const prev = i > 0 ? s.runs[i - 1].score : null;
                const delta = prev !== null ? r.score - prev : null;
                const thin = r.score >= 60 && r.cov <= 2;
                return (
                  <Link href={`/investigasi/${r.id}`} className="rw-row" key={r.id}>
                    <span className="rw-date">{r.date}</span>
                    <span className="rw-score" style={{ color: SIG[r.cls] }}>{r.score}</span>
                    <span className="rw-badge" style={{ color: SIG[r.cls], background: `color-mix(in srgb, ${SIG[r.cls]} 13%, transparent)` }}>{r.label}</span>
                    <span className="rw-cov">{r.cov}/{r.covTotal} komponen{thin && <span className="rw-thin" title="skor tinggi dari sedikit komponen"> ⚠</span>}</span>
                    <span className="rw-conf">keyakinan {r.conf}%</span>
                    {delta !== null && (
                      <span className={`rw-delta ${delta > 0 ? "up" : delta < 0 ? "down" : "flat"}`}>{delta > 0 ? "▲" : delta < 0 ? "▼" : "="}{delta !== 0 ? Math.abs(delta) : ""}</span>
                    )}
                    <span className="rw-moments">{r.moments.map((m) => <span className="rw-mtag" key={m}>{MOMENT[m] ?? m}</span>)}</span>
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function Tile({ n, k, accent }: { n: number | string; k: string; accent?: string }) {
  return (
    <div className="rw-tile">
      <div className="rw-tile-n" style={accent ? { color: accent } : undefined}>{n}</div>
      <div className="rw-tile-k">{k}</div>
    </div>
  );
}
