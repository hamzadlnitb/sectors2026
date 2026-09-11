import Link from "next/link";
import { bandMeta } from "@/lib/bands";
import type { IndexEntry } from "@/lib/transcript";

const SIG: Record<string, string> = {
  normal: "var(--sig-normal)",
  watch: "var(--sig-watch)",
  alert: "var(--sig-alert)",
  high: "var(--sig-danger)",
};

const MOMENT_BADGE: Record<string, string> = {
  escalation: "⤴ eskalasi",
  adaptive: "⟿ adaptif",
  early_stop: "berhenti dini",
  memory: "memori",
};

/** One row on the landing board / investigation index / alert board. */
export default function InvestigationCard({ e }: { e: IndexEntry }) {
  const band = bandMeta(e.band);
  const color = SIG[band.cls];
  // Show the most demonstrative agentic moment as a badge.
  const badge =
    e.moments.find((m) => m === "escalation") ??
    e.moments.find((m) => m === "adaptive") ??
    e.moments.find((m) => m === "early_stop");

  return (
    <Link className="card" href={`/investigasi/${e.id}`}>
      <span className="strip" style={{ background: color }} />
      <div className="cbody">
        <div className="crow">
          <span className="sym">{e.symbol}</span>
          <span className="sc">{e.pantau_score}</span>
        </div>
        <span className="band" style={{ color }}>
          <span className="bd" style={{ background: color }} /> {band.label}
        </span>
        <div className="why">{e.headline}</div>
        <div className="cmeta">
          <span>{e.steps} langkah</span>
          {badge && <span className="esc">{MOMENT_BADGE[badge]}</span>}
          <span>{e.credits_total} kredit</span>
        </div>
      </div>
    </Link>
  );
}
