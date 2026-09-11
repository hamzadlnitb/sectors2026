import Link from "next/link";
import { bandMeta } from "@/lib/bands";
import { fmtDate } from "@/lib/format";
import { loadIndex, type IndexEntry } from "@/lib/transcript";
import { loadWatchlist, loadWatchlistDates } from "@/lib/watchlist";
import "./papan.css";

const SIG: Record<string, string> = {
  normal: "var(--sig-normal)",
  watch: "var(--sig-watch)",
  alert: "var(--sig-alert)",
  high: "var(--sig-danger)",
};

const TOP_N = 8;

function utcTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = iso.match(/T(\d{2}):(\d{2})/);
  return m ? `${m[1]}:${m[2]} UTC` : "";
}

export default function PapanPage() {
  const index = loadIndex();
  const invBySymbol = new Map<string, IndexEntry>();
  for (const e of index.investigations) {
    const prev = invBySymbol.get(e.symbol);
    if (!prev || e.as_of > prev.as_of) invBySymbol.set(e.symbol, e);
  }

  const runs = loadWatchlistDates()
    .filter((d) => d.candidates > 0)
    .map((d) => ({ date: d, wl: loadWatchlist(d.as_of) }))
    .filter((r) => r.wl);

  return (
    <main>
      <div className="sec-label">
        <h2>Papan Waspada</h2>
        <span className="n">// arsip run otonom</span>
      </div>

      <div className="papan-intro">
        <span className="ic">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <div className="txt">
          Tiap hari bursa, cron <b>17:30 WIB</b> menyapu sinyal Tier-1, menyusun watchlist kandidat, lalu agen
          menyelidiki yang paling mencurigakan — <b>tanpa ditunggui manusia</b>. Ini arsipnya, ber-timestamp,
          bisa ditelusuri mundur. Skor kandidat di sini = skor <b>seleksi</b>, bukan skor PANTAU.
        </div>
      </div>

      {runs.length === 0 ? (
        <div className="panel" style={{ padding: "clamp(20px,4vw,32px)", marginTop: 16 }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>Belum ada run watchlist yang diekspor.</p>
        </div>
      ) : (
        runs.map(({ date, wl }) => {
          const cands = wl!.candidates.slice(0, TOP_N);
          const rest = wl!.candidates.length - cands.length;
          return (
            <div className="run" key={date.as_of}>
              <div className="run-head">
                <span className="date">{fmtDate(date.as_of)}</span>
                <span className="meta">
                  <span>{utcTime(date.generated_at)}</span>
                  <span><b>{wl!.candidates.length}</b> kandidat</span>
                  <span><b>{date.credits_spent ?? 0}</b> kredit</span>
                </span>
              </div>
              {cands.map((c, i) => {
                const inv = invBySymbol.get(c.symbol);
                const band = inv ? bandMeta(inv.band) : null;
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
                      {inv && band ? (
                        <Link href={`/investigasi/${inv.id}`} className="sel" style={{ color: SIG[band.cls], background: `color-mix(in srgb, ${SIG[band.cls]} 13%, transparent)` }}>
                          <span className="bd" style={{ background: SIG[band.cls] }} /> {band.label} · {inv.pantau_score}
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
              {rest > 0 && (
                <div className="cand" style={{ gridTemplateColumns: "1fr" }}>
                  <span className="why" style={{ textAlign: "center" }}>+ {rest} kandidat lain hari itu</span>
                </div>
              )}
            </div>
          );
        })
      )}

      <div className="footnote">
        arsip ditulis .github/workflows/daily.yml · zero API &amp; LLM calls saat web dibuka
      </div>
    </main>
  );
}
