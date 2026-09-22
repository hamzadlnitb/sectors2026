import Link from "next/link";
import { bandMeta } from "@/lib/bands";
import { fmtDate, wibTime } from "@/lib/format";
import type { ActivityEvent } from "@/lib/activity";

const PROBE_PENDEK: Record<string, string> = {
  volume_anomaly: "volume",
  broker_concentration: "broker",
  free_float: "free float",
  foreign_flow: "arus asing",
  structural: "struktural",
  price_fundamental: "harga vs laba",
};

const MOMEN: Record<string, { pendek: string; judul: string }> = {
  adaptive: { pendek: "perutean adaptif", judul: "Agen membuka probe di luar rencana awal" },
  early_stop: { pendek: "berhenti dini", judul: "Agen berhenti karena bukti sudah cukup" },
  escalation: { pendek: "eskalasi", judul: "Agen meminta tambahan pagu kredit" },
  memory: { pendek: "memori", judul: "Rencana disusun ulang memakai investigasi sebelumnya" },
};

const SIG: Record<string, string> = {
  normal: "var(--sig-normal)",
  watch: "var(--sig-watch)",
  alert: "var(--sig-alert)",
  high: "var(--sig-danger)",
};

export default function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) return null;
  return (
    <section className="activity">
      <div className="sec-label">
        <h2>Aktivitas agen</h2>
        <span className="n">Dicatat otomatis tiap hari bursa · {events.length} peristiwa</span>
      </div>
      <div className="feed">
        {events.map((e, i) =>
          e.kind === "investigation" ? <InvRow key={i} e={e} /> : <SweepRow key={i} e={e} />
        )}
      </div>
    </section>
  );
}

function SweepRow({ e }: { e: ActivityEvent }) {
  return (
    <div className="feed-row">
      <span className="fr-dot" style={{ background: "var(--accent)" }} />
      <div className="fr-body">
        <div className="fr-time mono">{fmtDate(e.date)} · {wibTime(e.ts)}</div>
        <div className="fr-title">Sapuan Tier-1 <span className="fr-kind mono">cron</span></div>
        <div className="fr-detail">
          <span className="mono">{e.candidates}</span> kandidat ditandai · <span className="mono">{e.credits ?? 0}</span> kredit
        </div>
      </div>
    </div>
  );
}

function InvRow({ e }: { e: ActivityEvent }) {
  const band = bandMeta(e.band ?? "normal");
  const color = SIG[band.cls];
  return (
    <div className="feed-row">
      <span className="fr-dot" style={{ background: color }} />
      <div className="fr-body">
        <div className="fr-time mono">{fmtDate(e.date)} · {wibTime(e.ts)}</div>
        <div className="fr-title">
          Investigasi{" "}
          {e.id ? <Link href={`/investigasi/${e.id}`}>{e.symbol}</Link> : <span>{e.symbol}</span>}{" "}
          <span className="fr-band mono" style={{ color }}>{band.label} · {e.pantau_score}</span>
        </div>
        <div className="fr-detail">
          <span className="mono">{e.steps}</span> langkah · <span className="mono">{e.credits}</span> kredit
          {typeof e.baseline_credits === "number" && (
            <> dari <span className="mono">{e.baseline_credits}</span> kalau semua probe dijalankan</>
          )}
          {typeof e.savings_pct === "number" && <> · hemat <span className="mono">{e.savings_pct}%</span></>}
          {typeof e.components_used === "number" && (
            <>
              {" "}·{" "}
              <span
                className={(e.confidence ?? 1) < 0.5 ? "hv-tipis" : undefined}
                title={`Skor dihitung dari ${e.components_used} dari ${e.components_total} komponen; sisanya datanya tidak tersedia.`}
              >
                <span className="mono">{e.components_used}/{e.components_total}</span> komponen
              </span>
            </>
          )}
        </div>

        {/* Urutan probe adalah jejak keputusan agen: apa yang dikejar lebih dulu,
            apa yang dibuka di luar rencana, dan di mana ia berhenti. Tanpa ini,
            feed cuma membuktikan ada proses yang jalan, bukan ada yang memilih. */}
        {e.trail && e.trail.length > 0 && (
          <div className="fr-trail">
            {e.trail.map((t, i) => (
              <span
                key={i}
                className={`fr-probe ${t.finding}${t.planned ? "" : " unplanned"}`}
                title={
                  `${i + 1}. ${PROBE_PENDEK[t.probe] ?? t.probe} → ${t.finding}` +
                  ` · ${t.credits} kredit` +
                  (t.planned ? "" : " · dibuka di luar rencana awal")
                }
              >
                {PROBE_PENDEK[t.probe] ?? t.probe}
              </span>
            ))}
          </div>
        )}

        {e.moments && e.moments.length > 0 && (
          <div className="fr-momen">
            {e.moments.map((m) => (
              <span key={m} className="fr-badge" title={MOMEN[m]?.judul ?? m}>
                {MOMEN[m]?.pendek ?? m}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
