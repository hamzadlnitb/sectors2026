import Link from "next/link";
import SearchBox from "@/components/SearchBox";
import InvestigationCard from "@/components/InvestigationCard";
import ActivityFeed from "@/components/ActivityFeed";
import LandingChat from "@/components/LandingChat";
import { loadIndex, symbolToId } from "@/lib/transcript";
import { loadActivity } from "@/lib/activity";
import { bandMeta } from "@/lib/bands";
import "./landing.css";

const PROCESS = [
  { n: "1", w: "Deteksi otomatis", d: "Tiap hari bursa, agen menyapu pasar dan menandai saham yang bergerak tidak wajar, tanpa kamu perlu memantau layar." },
  { n: "2", w: "Selidiki sendiri", d: "Agen memilih bukti mana yang dikejar, menguji tiap dugaan, lalu berhenti begitu buktinya sudah cukup." },
  { n: "3", w: "Terbuka, bisa dicek", d: "Hasilnya skor plus cerita yang bisa dicek sampai ke sumber datanya, bukan kotak hitam." },
];

const SIGNALS = [
  { code: "BCI", name: "Konsentrasi broker", d: "Pembelian menumpuk di segelintir broker saja?" },
  { code: "VAS", name: "Anomali volume", d: "Volume melonjak jauh di atas kebiasaannya?" },
  { code: "PFD", name: "Harga vs fundamental", d: "Harga melompat padahal laba datar atau rugi?" },
  { code: "FFS", name: "Saham beredar tipis", d: "Barang langka di pasar sehingga mudah digerakkan?" },
  { code: "FRD", name: "Asing vs ritel", d: "Asing keluar saat harga naik, dilempar ke ritel?" },
  { code: "SSS", name: "Peristiwa struktural", d: "Suspensi, rights issue beruntun, atau insider jual?" },
];

export default function Landing() {
  const index = loadIndex();
  const routes = symbolToId(index);
  const rows = index.investigations.slice(0, 6);
  const flagged = index.investigations.filter((e) => e.band === "waspada" || e.band === "sangat_waspada").length;
  const escalated = index.investigations.filter((e) => e.moments.includes("escalation")).length;
  const activity = loadActivity();
  // Sorotan kolom kanan hero: urut menurut skor x keyakinan, bukan skor mentah,
  // supaya yang tampil sinyal paling kredibel, bukan skor 100 dari 1 komponen.
  const ranked = [...index.investigations].sort(
    (a, b) => b.pantau_score * b.confidence - a.pantau_score * a.confidence,
  );
  const featured = ranked[0] ?? null;
  // Baris samping: satu per emiten (selain yang disorot) biar terlihat ragam pantauan.
  const seen = new Set(featured ? [featured.symbol] : []);
  const sideRows = ranked.filter((e) => !seen.has(e.symbol) && seen.add(e.symbol)).slice(0, 3);
  // Label "update <tanggal>" dari investigasi paling baru.
  const MO = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  const lastDate = index.investigations.reduce((m, e) => (e.as_of > m ? e.as_of : m), index.investigations[0]?.as_of ?? "");
  const [, lm, ld] = lastDate ? lastDate.slice(0, 10).split("-").map(Number) : [0, 1, 0];
  const updateLabel = lastDate ? `update ${ld} ${MO[(lm || 1) - 1]}` : "update";

  return (
    <main className="lp">
      <div className="lp-bg" aria-hidden="true">
        <span className="lp-orb a" />
      </div>
      <section className="hero">
        <div className="hero-main">
          <span className="eyebrow">Agen investigasi saham IDX</span>
          <h1>
            Saham ini ramai. Tapi siapa yang sebenarnya <span className="hl">menggerakkannya</span>?
          </h1>
          <p className="sub">
            PANTAU menyelidiki saham yang bergerak tidak wajar, lalu <b>menunjukkan langkah
            demi langkah</b> bagaimana ia sampai ke kesimpulan, bukan cuma memberi angka.
          </p>
          <SearchBox routes={routes} />
          {rows.length > 0 && (
            <div className="lp-eg">
              <span>Coba lihat:</span>
              {rows.slice(0, 3).map((e) => (
                <Link key={e.id} href={`/investigasi/${e.id}/`} className="eg">{e.symbol}</Link>
              ))}
            </div>
          )}
          <div className="microcopy">
            Ketik kode saham mana pun, lihat bagaimana agen menilainya.
          </div>
        </div>

        {featured && (
          <aside className="hero-side" aria-label="Sorotan investigasi">
            <div className="hs-head">
              <span className="hs-live"><span className="dot" /> {updateLabel}</span>
              <span className="hs-meta mono">{index.investigations.length} investigasi</span>
            </div>
            <Link href={`/investigasi/${featured.id}/`} className="hs-feat">
              <div className="hs-feat-top">
                <span className="hs-sym">{featured.symbol} <small>· IDX</small></span>
                <span className={`bandchip ${bandMeta(featured.band).cls}`}><span className="d" /> {bandMeta(featured.band).label}</span>
              </div>
              <div className="hs-score mono">{featured.pantau_score}<small>/100</small></div>
              {featured.headline && <div className="hs-headline">{featured.headline}</div>}
              <div className="hs-foot mono">{featured.steps} langkah · keyakinan {Math.round(featured.confidence * 100)}%</div>
            </Link>
            {sideRows.length > 0 && (
              <div className="hs-list">
                {sideRows.map((e) => (
                  <Link key={e.id} href={`/investigasi/${e.id}/`} className="hs-row">
                    <span className="hs-rsym mono">{e.symbol}</span>
                    <span className={`hs-rband ${bandMeta(e.band).cls}`}>{bandMeta(e.band).label}</span>
                    <span className="hs-rscore mono">{e.pantau_score}</span>
                  </Link>
                ))}
              </div>
            )}
          </aside>
        )}
      </section>

      <section>
        <div className="lp-head">
          <h2>Cara kerja</h2>
          <p>Tiga langkah: dari menandai saham yang mencurigakan sampai menjelaskan temuannya.</p>
        </div>
        <div className="process">
          {PROCESS.map((p) => (
            <div className="pstep" key={p.n}>
              <div className="pn">{p.n}</div>
              <div className="pw">{p.w}</div>
              <div className="pd">{p.d}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="lp-head">
          <h2>Yang diperiksa agen</h2>
          <p>Enam pola yang sering muncul saat sebuah saham digerakkan tidak wajar.</p>
        </div>
        <div className="signals">
          {SIGNALS.map((s) => (
            <div className="sig" key={s.code}>
              <span className="sc">{s.code}</span>
              <div>
                <div className="sn">{s.name}</div>
                <div className="sd">{s.d}</div>
              </div>
            </div>
          ))}
        </div>
        <Link href="/metodologi" className="sig-more">Lihat cara agen menghitung skornya →</Link>
      </section>

      <section className="board">
        <div className="board-head">
          <div className="bh-title">
            <h2>Investigasi hari ini</h2>
            <p>Hasil terbaru dari agen, ketuk salah satu untuk lihat langkah lengkapnya.</p>
          </div>
          <div className="board-stats">
            <span><b>{index.investigations.length}</b> diselidiki</span>
            <span><span className="d" style={{ background: "var(--sig-alert)" }} /><b>{flagged}</b> perlu perhatian</span>
            <span><span className="d" style={{ background: "var(--accent)" }} /><b>{escalated}</b> minta jatah tambah</span>
          </div>
        </div>
        <div className="cards">
          {rows.map((e) => (
            <InvestigationCard key={e.id} e={e} />
          ))}
        </div>
        <div className="autobar">
          <span className="ai">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="at">
            Tiap hari bursa pukul <b>17:30 WIB</b>, agen menyapu pasar dan menyelidiki sendiri, tanpa ditunggui.
          </span>
          <Link href="/papan">Lihat Papan Waspada →</Link>
        </div>
      </section>

      <LandingChat items={index.investigations} />

      <ActivityFeed events={activity.events.slice(0, 12)} />

      <div className="footnote">
        Semua ditampilkan dari data yang sudah tersimpan, tanpa panggilan API atau AI saat halaman dibuka.
      </div>
    </main>
  );
}
