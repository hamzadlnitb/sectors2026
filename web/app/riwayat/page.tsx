import type { Metadata } from "next";
import { bandMeta } from "@/lib/bands";
import { loadIndex, type IndexEntry } from "@/lib/transcript";
import RiwayatDashboard, { type RiwayatRun, type RiwayatSeries } from "@/components/RiwayatDashboard";
import "./riwayat.css";

export const metadata: Metadata = {
  title: "Riwayat analisa",
  description: "Dashboard tren skor tiap emiten dari hari ke hari, lengkap dengan cakupan komponen dan keyakinan.",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
function shortDate(iso: string): string {
  const [, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[(m || 1) - 1]}`;
}

export default function RiwayatPage() {
  const { investigations } = loadIndex();

  const bySymbol = new Map<string, IndexEntry[]>();
  for (const e of investigations) {
    const arr = bySymbol.get(e.symbol);
    if (arr) arr.push(e);
    else bySymbol.set(e.symbol, [e]);
  }

  const series: RiwayatSeries[] = [...bySymbol.entries()]
    .map(([symbol, arr]) => ({
      symbol,
      runs: [...arr]
        .sort((a, b) => a.as_of.localeCompare(b.as_of))
        .map((e): RiwayatRun => {
          const b = bandMeta(e.band);
          return {
            as_of: e.as_of,
            date: shortDate(e.as_of),
            score: e.pantau_score,
            band: e.band,
            cls: b.cls,
            label: b.label,
            cov: e.components_investigated,
            covTotal: e.components_total,
            conf: Math.round(e.confidence * 100),
            moments: e.moments.filter((m) => m !== "early_stop"),
            id: e.id,
          };
        }),
    }))
    .sort((a, b) => b.runs.length - a.runs.length || a.symbol.localeCompare(b.symbol));

  const summary = {
    total: investigations.length,
    symbols: series.length,
    flagged: investigations.filter((e) => e.band !== "normal").length,
    avgCov: investigations.length
      ? investigations.reduce((s, e) => s + e.components_investigated, 0) / investigations.length
      : 0,
  };

  return (
    <main>
      <div className="page-head">
        <h1>Riwayat analisa</h1>
        <p>Tren skor tiap emiten dari hari ke hari. Perhatikan cakupan: skor tinggi dari sedikit komponen berarti keyakinan rendah, jangan dibaca sebagai kepastian.</p>
      </div>

      {series.length === 0 ? (
        <div className="panel" style={{ padding: "clamp(20px,4vw,32px)" }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>Belum ada investigasi.</p>
        </div>
      ) : (
        <RiwayatDashboard series={series} summary={summary} />
      )}

      <div className="footnote">
        Diputar dari data tersimpan, tanpa panggilan API atau AI saat halaman dibuka.
      </div>
    </main>
  );
}
