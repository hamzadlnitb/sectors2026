import type { Metadata } from "next";
import Link from "next/link";
import { bandMeta } from "@/lib/bands";
import { fmtDate } from "@/lib/format";
import { loadIndex, type IndexEntry } from "@/lib/transcript";
import "./riwayat.css";

export const metadata: Metadata = {
  title: "Riwayat analisa",
  description: "Jejak skor tiap emiten dari hari ke hari, lengkap dengan cakupan komponen dan keyakinan.",
};

const SIG: Record<string, string> = {
  normal: "var(--sig-normal)",
  watch: "var(--sig-watch)",
  alert: "var(--sig-alert)",
  high: "var(--sig-danger)",
};
const MOMENT: Record<string, string> = {
  adaptive: "adaptif",
  escalation: "eskalasi",
  early_stop: "berhenti dini",
  memory: "memori",
};

export default function RiwayatPage() {
  const { investigations } = loadIndex();

  const bySymbol = new Map<string, IndexEntry[]>();
  for (const e of investigations) {
    const arr = bySymbol.get(e.symbol);
    if (arr) arr.push(e);
    else bySymbol.set(e.symbol, [e]);
  }
  const groups = [...bySymbol.entries()]
    .map(([sym, arr]) => ({ sym, runs: [...arr].sort((a, b) => a.as_of.localeCompare(b.as_of)) }))
    .sort((a, b) => b.runs.length - a.runs.length || a.sym.localeCompare(b.sym));

  return (
    <main>
      <div className="page-head">
        <h1>Riwayat analisa</h1>
        <p>Jejak skor tiap emiten dari hari ke hari. Angka cakupan penting: skor tinggi dari sedikit komponen berarti keyakinan rendah, jangan dibaca sebagai kepastian.</p>
      </div>

      {groups.length === 0 ? (
        <div className="panel" style={{ padding: "clamp(20px,4vw,32px)" }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>Belum ada investigasi.</p>
        </div>
      ) : (
        <div className="rw-list">
          {groups.map((g) => <SymbolHistory key={g.sym} sym={g.sym} runs={g.runs} />)}
        </div>
      )}

      <div className="footnote">
        Diputar dari data tersimpan, tanpa panggilan API atau AI saat halaman dibuka.
      </div>
    </main>
  );
}

function Spark({ runs }: { runs: IndexEntry[] }) {
  const step = 34;
  const h = 46;
  const pad = 7;
  const w = Math.max(runs.length - 1, 1) * step + pad * 2;
  const pt = (r: IndexEntry, i: number): [number, number] => [
    pad + i * step,
    h - pad - (r.pantau_score / 100) * (h - pad * 2),
  ];
  const pts = runs.map(pt);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  return (
    <svg className="rw-spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" role="img" aria-label="tren skor">
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth="1.6" strokeLinejoin="round" opacity="0.7" />
      {runs.map((r, i) => (
        <circle key={r.id} cx={pts[i][0]} cy={pts[i][1]} r={3.4} fill={SIG[bandMeta(r.band).cls]} />
      ))}
    </svg>
  );
}

function SymbolHistory({ sym, runs }: { sym: string; runs: IndexEntry[] }) {
  const first = runs[0];
  const last = runs[runs.length - 1];
  return (
    <section className="rw-card">
      <div className="rw-head">
        <span className="rw-sym">{sym}</span>
        <span className="rw-range">{runs.length} investigasi · {fmtDate(first.as_of)} – {fmtDate(last.as_of)}</span>
        {runs.length > 1 && <Spark runs={runs} />}
      </div>
      <div className="rw-rows">
        {runs.map((r, i) => {
          const b = bandMeta(r.band);
          const color = SIG[b.cls];
          const prev = i > 0 ? runs[i - 1].pantau_score : null;
          const delta = prev !== null ? r.pantau_score - prev : null;
          const thin = r.pantau_score >= 60 && r.components_investigated <= 2;
          return (
            <Link href={`/investigasi/${r.id}`} className="rw-row" key={r.id}>
              <span className="rw-date">{fmtDate(r.as_of)}</span>
              <span className="rw-score" style={{ color }}>{r.pantau_score}</span>
              <span className="rw-badge" style={{ color, background: `color-mix(in srgb, ${color} 13%, transparent)` }}>{b.label}</span>
              <span className="rw-cov" title="komponen yang benar-benar diselidiki">
                {r.components_investigated}/{r.components_total} komponen
                {thin && <span className="rw-thin" title="skor tinggi dari sedikit komponen, keyakinan rendah"> ⚠</span>}
              </span>
              <span className="rw-conf">keyakinan {Math.round(r.confidence * 100)}%</span>
              {delta !== null && (
                <span className={`rw-delta ${delta > 0 ? "up" : delta < 0 ? "down" : "flat"}`}>
                  {delta > 0 ? "▲" : delta < 0 ? "▼" : "="}{delta !== 0 ? Math.abs(delta) : ""}
                </span>
              )}
              <span className="rw-moments">
                {r.moments.filter((m) => m !== "early_stop").map((m) => (
                  <span className="rw-mtag" key={m}>{MOMENT[m] ?? m}</span>
                ))}
              </span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
