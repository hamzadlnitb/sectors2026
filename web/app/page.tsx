import Link from "next/link";
import SearchBox from "@/components/SearchBox";
import InvestigationCard from "@/components/InvestigationCard";
import { loadIndex, symbolToId } from "@/lib/transcript";
import "./landing.css";

const PROCESS = [
  { n: "01", w: "DETECT", d: "Menyapu sinyal Tier-1 pasar tiap hari bursa dan menandai saham yang bergerak tidak biasa." },
  { n: "02", w: "INVESTIGATE", d: "Agen memilih bukti apa yang dikejar, menguji tiap hipotesis, dan berhenti begitu bukti cukup." },
  { n: "03", w: "EXPLAIN", d: "Skor deterministik + narasi tersitasi — tiap angka bisa ditelusuri ke endpoint sumbernya." },
];

const SIGNALS = [
  { code: "BCI", name: "Broker Concentration", d: "Net-buy terkonsentrasi di segelintir broker?" },
  { code: "VAS", name: "Volume Anomaly", d: "Volume berapa sigma di atas baseline 90 hari?" },
  { code: "PFD", name: "Price–Fundamental", d: "Harga melompat sementara laba flat atau rugi?" },
  { code: "FFS", name: "Free Float", d: "Saham beredar langka sehingga mudah digerakkan?" },
  { code: "FRD", name: "Foreign–Retail", d: "Asing keluar saat harga naik = distribusi ke ritel?" },
  { code: "SSS", name: "Structural", d: "Suspensi, rights issue beruntun, insider jual?" },
];

export default function Landing() {
  const index = loadIndex();
  const routes = symbolToId(index);
  const rows = index.investigations.slice(0, 6);
  const flagged = index.investigations.filter((e) => e.band === "waspada" || e.band === "sangat_waspada").length;
  const escalated = index.investigations.filter((e) => e.moments.includes("escalation")).length;

  return (
    <main>
      <section className="hero">
        <span className="eyebrow">
          <span className="live" /> Investigator Agent · IDX
        </span>
        <h1>
          Saham ini ramai. Tapi, siapa yang sebenarnya <span className="hl">menggerakkannya</span>?
          <span className="cur" />
        </h1>
        <p className="sub">
          PANTAU menyelidiki pergerakan saham seperti analis sungguhan—mengejar bukti yang relevan,
          menguji hipotesis, dan <b>menunjukkan jejak menuju kesimpulan</b>.
        </p>
        <SearchBox routes={routes} />
        <div className="microcopy">
          <span className="tick">▸</span> Evidence-first. Setiap temuan dapat ditelusuri ke buktinya.
        </div>
      </section>

      <section>
        <div className="sec-label"><h2>Cara kerja</h2><span className="n">// detect · investigate · explain</span></div>
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
        <div className="sec-label"><h2>Enam sinyal yang dicek</h2><span className="n">// enam komponen skor</span></div>
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
        <Link href="/metodologi" className="sig-more">Lihat rumus &amp; bobot kalibrasi →</Link>
      </section>

      <section className="board">
        <div className="board-head">
          <h2>Investigasi hari ini</h2>
          <div className="board-stats">
            <span><b>{index.investigations.length}</b> diselidiki</span>
            <span><span className="d" style={{ background: "var(--sig-alert)" }} /><b>{flagged}</b> ditandai</span>
            <span><span className="d" style={{ background: "var(--accent)" }} /><b>{escalated}</b> eskalasi</span>
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
            Berjalan sendiri — tiap hari bursa pukul <b>17:30 WIB</b>, agen menyapu, menyeleksi, dan menyelidiki tanpa ditunggui.
          </span>
          <Link href="/papan">Lihat Papan Waspada →</Link>
        </div>
      </section>

      <div className="disclaimer">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <circle cx="12" cy="12" r="9.5" />
          <path d="M12 8v5" strokeLinecap="round" />
          <circle cx="12" cy="16.4" r="0.4" fill="currentColor" stroke="none" />
        </svg>
        PANTAU adalah alat informasi dan analisis, bukan saran investasi.
      </div>
      <div className="footnote">
        zero API &amp; LLM calls at runtime · web hanya memutar ulang transkrip investigasi tersimpan
      </div>
    </main>
  );
}
