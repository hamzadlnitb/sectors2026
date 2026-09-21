import type { Metadata } from "next";
import PapanBrowser, { type InvRef, type PapanRun } from "@/components/PapanBrowser";
import type { Band } from "@/lib/bands";
import { loadIndex } from "@/lib/transcript";
import { loadWatchlist, loadWatchlistDates } from "@/lib/watchlist";
import { wibTime } from "@/lib/format";
import "./papan.css";

export const metadata: Metadata = {
  title: "Papan Waspada",
  description: "Arsip run otonom bertanggal, watchlist kandidat hasil sapuan Tier-1 harian, bisa ditelusuri mundur.",
};

export default function PapanPage() {
  const index = loadIndex();
  const invBySymbol: Record<string, InvRef> = {};
  for (const e of index.investigations) {
    const prev = invBySymbol[e.symbol];
    if (!prev) invBySymbol[e.symbol] = { id: e.id, band: e.band as Band, score: e.pantau_score };
  }

  const runs: PapanRun[] = loadWatchlistDates()
    .filter((d) => d.candidates > 0)
    .map((d) => {
      const wl = loadWatchlist(d.as_of);
      return wl
        ? {
            date: d.as_of,
            time: wibTime(d.generated_at),
            credits: d.credits_spent,
            candidateCount: wl.candidates.length,
            candidates: wl.candidates,
            runLog: wl.run_log ?? [],
          }
        : null;
    })
    .filter((r): r is PapanRun => r !== null);

  return (
    <main>
      <div className="page-head">
        <h1>Papan Waspada</h1>
        <p>Arsip pantauan harian yang berjalan sendiri, bisa ditelusuri per tanggal.</p>
      </div>

      {runs.length === 0 ? (
        <div className="panel" style={{ padding: "clamp(20px,4vw,32px)", marginTop: 16 }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>Belum ada run watchlist yang diekspor.</p>
        </div>
      ) : (
        <PapanBrowser runs={runs} invBySymbol={invBySymbol} />
      )}

      <div className="footnote">
        arsip ditulis .github/workflows/daily.yml · zero API &amp; LLM calls saat web dibuka
      </div>
    </main>
  );
}
