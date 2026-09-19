import Link from "next/link";
import { bandMeta } from "@/lib/bands";
import { fmtDate } from "@/lib/format";
import type { ActivityEvent } from "@/lib/activity";

const SIG: Record<string, string> = {
  normal: "var(--sig-normal)",
  watch: "var(--sig-watch)",
  alert: "var(--sig-alert)",
  high: "var(--sig-danger)",
};

function timeLabel(ts: string): string {
  const m = ts.match(/T(\d{2}):(\d{2}):\d{2}([+-]\d{2})/);
  if (!m) return "";
  const zone = m[3] === "+07" ? "WIB" : m[3] === "+00" ? "UTC" : `UTC${m[3]}`;
  return `${m[1]}:${m[2]} ${zone}`;
}

export default function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) return null;
  return (
    <section className="activity">
      <div className="sec-label">
        <h2>Aktivitas agen</h2>
        <span className="n">{"//"} otomatis dari runs/ · {events.length} peristiwa</span>
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
        <div className="fr-time mono">{fmtDate(e.date)} · {timeLabel(e.ts)}</div>
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
        <div className="fr-time mono">{fmtDate(e.date)} · {timeLabel(e.ts)}</div>
        <div className="fr-title">
          Investigasi{" "}
          {e.id ? <Link href={`/investigasi/${e.id}`}>{e.symbol}</Link> : <span>{e.symbol}</span>}{" "}
          <span className="fr-band mono" style={{ color }}>{band.label} · {e.pantau_score}</span>
        </div>
        <div className="fr-detail">
          <span className="mono">{e.steps}</span> langkah · <span className="mono">{e.credits}</span> kredit
          {typeof e.savings_pct === "number" && <> · hemat <span className="mono">{e.savings_pct}%</span></>}
        </div>
      </div>
    </div>
  );
}
