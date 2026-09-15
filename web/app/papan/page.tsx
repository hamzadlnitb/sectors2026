import PapanBrowser, { type InvRef, type PapanRun } from "@/components/PapanBrowser";
import type { Band } from "@/lib/bands";
import { loadIndex } from "@/lib/transcript";
import { loadWatchlist, loadWatchlistDates } from "@/lib/watchlist";
import "./papan.css";

const REPO_URL = "https://github.com/hamzadlnitb/sectors2026";

function utcTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = iso.match(/T(\d{2}):(\d{2})/);
  return m ? `${m[1]}:${m[2]} UTC` : "";
}

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
            time: utcTime(d.generated_at),
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
      <div className="sec-label">
        <h2>Papan Waspada</h2>
        <span className="n">{"//"} arsip run otonom</span>
      </div>

      <div className="papan-intro">
        <span className="ic">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <div className="txt">
          Tiap hari bursa, cron <b>17:30 WIB</b> menyapu sinyal Tier-1, menyusun watchlist kandidat, lalu agen
          menyelidiki yang paling mencurigakan — <b>tanpa ditunggui manusia</b>. Pilih tanggal untuk menelusuri arsipnya;
          tiap run ber-timestamp dan bisa diverifikasi ke commit <b>pantau-bot</b> di GitHub. Skor kandidat = skor
          <b> seleksi</b>, bukan skor PANTAU.
        </div>
      </div>

      {runs.length === 0 ? (
        <div className="panel" style={{ padding: "clamp(20px,4vw,32px)", marginTop: 16 }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>Belum ada run watchlist yang diekspor.</p>
        </div>
      ) : (
        <PapanBrowser runs={runs} invBySymbol={invBySymbol} repoUrl={REPO_URL} />
      )}

      <div className="footnote">
        arsip ditulis .github/workflows/daily.yml · zero API &amp; LLM calls saat web dibuka
      </div>
    </main>
  );
}
