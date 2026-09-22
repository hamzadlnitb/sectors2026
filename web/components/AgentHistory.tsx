import Link from "next/link";
import { bandMeta } from "@/lib/bands";
import { fmtDate } from "@/lib/format";
import type { SymbolHistory, HistoryRun } from "@/lib/history";

const SIG: Record<string, string> = {
  normal: "var(--sig-normal)",
  watch: "var(--sig-watch)",
  alert: "var(--sig-alert)",
  high: "var(--sig-danger)",
};

const MOMEN: Record<string, { pendek: string; judul: string }> = {
  adaptive: { pendek: "adaptif", judul: "Agen membuka probe di luar rencana awal" },
  early_stop: { pendek: "berhenti dini", judul: "Agen berhenti karena bukti sudah cukup" },
  escalation: { pendek: "eskalasi", judul: "Agen meminta tambahan pagu kredit" },
  memory: { pendek: "memori", judul: "Rencana disusun ulang memakai investigasi sebelumnya" },
};

/** "2026-09-10" → "10/9". Sumbu waktu harus muat di layar 375px. */
function tanggalPendek(iso: string): string {
  const [, m, d] = iso.slice(0, 10).split("-");
  return `${Number(d)}/${Number(m)}`;
}

export default function AgentHistory({ symbols }: { symbols: SymbolHistory[] }) {
  const berulang = symbols.filter((s) => s.kunjungan > 1);
  if (berulang.length === 0) return null;

  return (
    <section className="hist">
      <div className="sec-label">
        <h2>Riwayat analisa agen</h2>
        <span className="n">
          Emiten yang diselidiki lebih dari sekali, urut waktu. Yang dibaca di sini bukan
          skornya, melainkan apa yang berubah di antara dua kunjungan.
        </span>
      </div>

      <div className="hist-list">
        {berulang.map((s) => (
          <Kartu key={s.symbol} s={s} />
        ))}
      </div>
    </section>
  );
}

function Kartu({ s }: { s: SymbolHistory }) {
  const band = bandMeta(s.band_terakhir);
  const warna = SIG[band.cls];
  const naik = s.jejak[s.jejak.length - 1].pantau_score - s.jejak[0].pantau_score;

  return (
    <article className="hcard">
      <header className="hc-head">
        <div className="hc-id">
          <span className="hc-sym mono">{s.symbol}</span>
          <span className="hc-band mono" style={{ color: warna }}>
            {band.label} · {s.skor_terakhir}
          </span>
        </div>
        <div className="hc-meta">
          <span className="mono">{s.kunjungan}</span> kunjungan ·{" "}
          {fmtDate(s.pertama)} – {fmtDate(s.terakhir)} ·{" "}
          <span className="mono">{s.kredit_total}</span> kredit
          {naik !== 0 && (
            <>
              {" "}· skor <span className="mono">{naik > 0 ? `+${naik}` : naik}</span> sejak kunjungan pertama
            </>
          )}
        </div>
      </header>

      <Sparkline jejak={s.jejak} warna={warna} />

      <ol className="hc-trail">
        {s.jejak.map((r) => (
          <Kunjungan key={r.id} r={r} />
        ))}
      </ol>
    </article>
  );
}

/** Lintasan skor 0–100. viewBox tetap + preserveAspectRatio none: lebarnya ikut
 *  kartu, tingginya tidak, jadi bentuknya sama di 375px dan di desktop. */
function Sparkline({ jejak, warna }: { jejak: HistoryRun[]; warna: string }) {
  if (jejak.length < 2) return null;
  const W = 100;
  const H = 28;
  const x = (i: number) => (i / (jejak.length - 1)) * W;
  const y = (skor: number) => H - (skor / 100) * H;
  const titik = jejak.map((r, i) => `${x(i)},${y(r.pantau_score)}`).join(" ");

  return (
    <svg
      className="hc-spark"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`Lintasan skor ${jejak.map((r) => r.pantau_score).join(", ")}`}
    >
      <polyline points={titik} fill="none" stroke={warna} strokeWidth="1.2"
                vectorEffect="non-scaling-stroke" />
      {jejak.map((r, i) => (
        <circle key={r.id} cx={x(i)} cy={y(r.pantau_score)} r="1.6" fill={warna}
                vectorEffect="non-scaling-stroke" />
      ))}
    </svg>
  );
}

function Kunjungan({ r }: { r: HistoryRun }) {
  const band = bandMeta(r.band);
  const warna = SIG[band.cls];
  const adaptif = r.trail.filter((t) => !t.planned).length;
  // Setengah bobot ke bawah: skor sudah lebih ditentukan oleh komponen mana
  // yang kebetulan terukur daripada oleh emitennya.
  const tipis = r.confidence < 0.5;

  return (
    <li className="hv">
      <Link href={`/investigasi/${r.id}/`} className="hv-link">
        <span className="hv-tgl mono" title={fmtDate(r.as_of)}>{tanggalPendek(r.as_of)}</span>
        <span className="hv-skor mono" style={{ color: warna }}>{r.pantau_score}</span>
        {r.delta_score === null ? (
          <span className="hv-delta hv-first" title="Kunjungan pertama, belum ada pembanding">
            pertama
          </span>
        ) : r.delta_score === 0 ? (
          <span className="hv-delta hv-flat" title="Skor tidak berubah">tetap</span>
        ) : (
          <span
            className={`hv-delta mono ${r.delta_score > 0 ? "hv-up" : "hv-down"}`}
            title={`Berubah ${r.delta_score} dari kunjungan sebelumnya`}
          >
            {r.delta_score > 0 ? `▲ ${r.delta_score}` : `▼ ${Math.abs(r.delta_score)}`}
          </span>
        )}
      </Link>

      <div className="hv-body">
        <div className="hv-kerja">
          <span className="mono">{r.steps}</span> langkah ·{" "}
          <span className="mono">{r.credits_total}</span> kredit ·{" "}
          {/* Skor dinormalkan ulang atas komponen yang tersedia. Tanpa angka
              ini, "100 · 1 langkah · hemat" terbaca sebagai efisien, padahal
              artinya cuma satu dari enam komponen yang benar-benar terukur. */}
          <span className={tipis ? "hv-tipis" : "mono"}
                title={`Skor dihitung dari ${r.components_used} dari ${r.components_total} komponen; sisanya datanya tidak tersedia. Keyakinan ${Math.round(r.confidence * 100)}%.`}>
            <span className="mono">{r.components_used}/{r.components_total}</span> komponen
          </span>
          {adaptif > 0 && (
            <>
              {" "}· <span className="mono">{adaptif}</span> di luar rencana
            </>
          )}
          {r.narrative_source === "template" && (
            <span className="hv-tmpl" title="Validator menolak keluaran LLM; narasi jatuh ke template deterministik">
              narasi template
            </span>
          )}
        </div>
        {r.moments.length > 0 && (
          <div className="hv-momen">
            {r.moments.map((m) => (
              <span key={m} className="hv-badge" title={MOMEN[m]?.judul ?? m}>
                {MOMEN[m]?.pendek ?? m}
              </span>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}
