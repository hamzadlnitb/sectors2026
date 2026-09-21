import type { Metadata } from "next";
import InvestigationCard from "@/components/InvestigationCard";
import { loadIndex } from "@/lib/transcript";

export const metadata: Metadata = {
  title: "Semua investigasi",
  description: "Arsip investigasi otonom PANTAU atas saham IDX, skor, band, dan jejak penalaran tiap emiten.",
};

export default function InvestigasiIndex() {
  const { investigations } = loadIndex();

  return (
    <main>
      <div className="page-head">
        <h1>Investigasi</h1>
        <p>{investigations.length} investigasi tersimpan, diputar dari rekaman.</p>
      </div>

      {investigations.length === 0 ? (
        <div className="panel" style={{ padding: "clamp(20px,4vw,32px)" }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>
            Belum ada rekaman. Jalankan <span className="mono">python -m core.export.to_json</span> untuk mengisi data.
          </p>
        </div>
      ) : (
        <div className="cards">
          {investigations.map((e) => (
            <InvestigationCard key={e.id} e={e} />
          ))}
        </div>
      )}

      <div className="footnote">Semua dari data tersimpan, tanpa panggilan API atau AI saat halaman dibuka.</div>
    </main>
  );
}
