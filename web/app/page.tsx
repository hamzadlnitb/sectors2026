import SearchBox from "@/components/SearchBox";
import InvestigationCard from "@/components/InvestigationCard";
import { loadIndex, symbolToId } from "@/lib/transcript";
import "./landing.css";

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
          <span className="live" /> Investigator Saham AI · IDX
        </span>
        <h1>
          Saham lagi ramai. Nyata, atau <span className="hl">digoreng</span>?
          <span className="cur" />
        </h1>
        <p className="sub">
          Selidiki saham IDX seperti analis — PANTAU memutuskan sendiri bukti apa yang dikejar,
          lalu memperlihatkan <b>tiap langkah buktinya</b>.
        </p>
        <SearchBox routes={routes} />
        <div className="microcopy">
          <span className="tick">▸</span> Nol saran investasi. Tiap angka bisa ditelusuri ke sumbernya.
        </div>
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
