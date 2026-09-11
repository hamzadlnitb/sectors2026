import InvestigationCard from "@/components/InvestigationCard";
import { loadIndex } from "@/lib/transcript";

export default function InvestigasiIndex() {
  const { investigations } = loadIndex();

  return (
    <main>
      <div className="sec-label">
        <h2>Investigasi</h2>
        <span className="n">// {investigations.length} tersimpan · diputar ulang dari transkrip</span>
      </div>

      {investigations.length === 0 ? (
        <div className="panel" style={{ padding: "clamp(20px,4vw,32px)" }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>
            Belum ada transkrip. Jalankan <span className="mono">python -m core.export.to_json</span> untuk mengisi data.
          </p>
        </div>
      ) : (
        <div className="cards">
          {investigations.map((e) => (
            <InvestigationCard key={e.id} e={e} />
          ))}
        </div>
      )}

      <div className="footnote">zero API &amp; LLM calls at runtime · web hanya membaca transkrip statis</div>
    </main>
  );
}
