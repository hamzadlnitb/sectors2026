import type { Metadata } from "next";
import Link from "next/link";
import ReplayTimeline, { type RenderStep } from "@/components/ReplayTimeline";
import EvidenceVerdict from "@/components/EvidenceVerdict";
import AgentChat from "@/components/AgentChat";
import { bandMeta } from "@/lib/bands";
import { fmtDate } from "@/lib/format";
import {
  detectMoments,
  gaugeDot,
  listInvestigationIds,
  loadInvestigation,
  savingsPct,
  type Moment,
} from "@/lib/transcript";
import "../investigasi.css";

const ARC = "M20 150 A120 120 0 0 1 260 150";

export function generateStaticParams() {
  return listInvestigationIds().map((id) => ({ id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const t = loadInvestigation(id);
  const band = bandMeta(t.band);
  const title = `Investigasi ${t.symbol}, ${band.label}`;
  const description = `Skor PANTAU ${t.pantau_score}/100 (${band.label}) untuk ${t.symbol} · ${t.steps.length} langkah investigasi otonom, tiap angka tertelusuri ke buktinya. Bukan saran investasi.`;
  return { title, description, openGraph: { title, description }, twitter: { title, description } };
}

export default async function InvestigationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = loadInvestigation(id);
  const band = bandMeta(t.band);
  const dot = gaugeDot(t.pantau_score);
  const moments = detectMoments(t);
  const confidencePct = Math.round(t.confidence * 100);
  const creditsPct = t.baseline_credits ? Math.round((t.credits_total / t.baseline_credits) * 100) : 0;
  const sav = savingsPct(t); // bisa negatif sejak C6 (agen bisa lebih boros dari baseline)

  const tagByStep = new Map<number, string>();
  for (const m of moments) {
    if (m.kind === "adaptive") tagByStep.set(m.step, "⟿ perutean adaptif");
    if (m.kind === "escalation" && !tagByStep.has(m.step)) tagByStep.set(m.step, "↑ eskalasi");
    if (m.kind === "early_stop" && !tagByStep.has(m.step)) tagByStep.set(m.step, "■ berhenti dini");
  }
  const steps: RenderStep[] = t.steps.map((s) => ({ ...s, tag: tagByStep.get(s.step) }));

  return (
    <main>
      <Link href="/investigasi" className="crumb mono">← semua investigasi</Link>

      {/* ── Verdict ── */}
      <div className="panel">
        <div className="panel-head">
          <span className="dots"><i /><i /><i /></span>
          <span className="t mono">investigasi · <b>{t.symbol}</b></span>
          <span className="r mono">selesai · {fmtDate(t.as_of)}</span>
        </div>
        <div className="verdict">
          <div className="gauge-wrap">
            <svg className="gauge" viewBox="0 0 280 172" role="img" aria-label={`PANTAU score ${t.pantau_score} of 100, ${band.label}`}>
              <path className="track" d={ARC} pathLength={100} />
              <path className={`val ${band.cls}`} d={ARC} pathLength={100} strokeDasharray={`${t.pantau_score} 100`} />
              <circle className={`dot ${band.cls}`} cx={dot.x} cy={dot.y} r={7.5} />
              <text x={140} y={130} textAnchor="middle" className="gscore" fill="var(--text)">{t.pantau_score}</text>
              <text x={140} y={156} textAnchor="middle" className="gden" fill="var(--dim)">/ 100</text>
            </svg>
            <div className={`bandchip on-gauge ${band.cls}`}><span className="d" /> {band.label}</div>
          </div>
          <div>
            <h1 className="vtitle"><span className="tk">{t.symbol}</span> · IDX</h1>
            <div className="vsub mono">Investigasi otonom · <b>{t.steps.length} langkah</b> · <b>{t.credits_total} kredit</b></div>
            <div className="stats">
              <div className="stat">
                <div className="k">Keyakinan</div>
                <div className="v">{confidencePct}<small>%</small></div>
                <div className="bar"><i style={{ width: `${confidencePct}%`, background: "var(--accent)" }} /></div>
              </div>
              <div className="stat">
                <div className="k">Kredit vs baseline</div>
                <div className="v">{t.credits_total}<small> / {t.baseline_credits}</small></div>
                <div className="bar"><i style={{ width: `${creditsPct}%`, background: "var(--sig-normal)" }} /></div>
              </div>
              <div className="stat wide">
                <div className="k">Hemat agen</div>
                <div className={`v ${sav >= 0 ? "good" : "bad"}`}>
                  {sav >= 0 ? `−${sav}%` : `+${-sav}%`}
                  <small> {sav >= 0 ? "kredit vs investigasi menyeluruh (6 probe)" : "kredit lebih dari investigasi menyeluruh (agen kalah)"}</small>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Agentic moments ── */}
      {moments.length > 0 && (
        <section>
          <div className="sec-label"><h2>Momen kunci agen</h2><span className="n">yang membedakannya dari if-else</span></div>
          <div className="moments">
            {moments.map((m) => <MomentCard key={m.kind} m={m} />)}
          </div>
          {t.memory_ref && (
            <div className="memory">
              <span className="ic"><MemoryIcon /></span>
              <div className="txt">
                Agen mengingat investigasi sebelumnya. Rencana kali ini <b>menahan jatah di awal</b> karena run{" "}
                <a href="#">{t.memory_ref}</a> berakhir normal, bukan mengulang dari nol.
              </div>
            </div>
          )}
        </section>
      )}

      {/* ── Plan ── */}
      <section>
        <div className="sec-label"><h2>Rencana investigasi</h2><span className="n">disusun sebelum menyelidiki</span></div>
        <div className="panel">
          <div className="plan-top">
            <span className="lbl">{t.plan.hypotheses.length} dugaan, urut prioritas</span>
            <span className="bud">jatah diminta <b>{t.plan.credit_budget_requested} kredit</b> · batas keras 25</span>
          </div>
          <div className="hyps">
            {t.plan.hypotheses.map((h) => (
              <div className="hyp" key={h.id}>
                <span className="pri mono">H{h.priority}</span>
                <div>
                  <div className="claim">{h.claim}</div>
                  <div className="probes">
                    {h.probes.map((p) => <span className="ptag" key={p}>{p}</span>)}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="rationale">&ldquo;{t.plan.rationale}&rdquo;</div>
        </div>
      </section>

      {/* ── Reasoning replay ── */}
      <section>
        <div className="sec-label"><h2>Putar ulang penalaran</h2><span className="n">langkah demi langkah</span></div>
        <ReplayTimeline steps={steps} />
      </section>

      {/* ── Evidence + verdict ── */}
      <EvidenceVerdict evidence={t.evidence} narrative={t.narrative} narrativeSource={t.narrative_source} />

      {/* ── Chat walkthrough (static, grounded ke rekaman) ── */}
      <AgentChat
        symbol={t.symbol}
        band={t.band}
        score={t.pantau_score}
        confidence={t.confidence}
        creditsTotal={t.credits_total}
        baseline={t.baseline_credits}
        savings={savingsPct(t)}
        steps={t.steps}
        evidence={t.evidence}
        moments={moments}
        memoryRef={t.memory_ref ?? null}
      />

      <div className="footnote">Diputar dari rekaman tersimpan · tanpa panggilan API atau AI saat dibuka · {t.symbol} · {t.weights_version}</div>
    </main>
  );
}

function MomentCard({ m }: { m: Moment }) {
  const view = {
    adaptive: {
      title: "Perutean adaptif",
      at: `langkah ${"step" in m ? m.step : ""}`,
      icon: <AdaptiveIcon />,
      desc: <>Membuka <code>{m.kind === "adaptive" ? m.probe : ""}</code>, probe di luar rencana awal.</>,
    },
    escalation: {
      title: "Eskalasi",
      at: `langkah ${"step" in m ? m.step : ""}`,
      icon: <EscalationIcon />,
      desc: <>Minta tambah jatah <code>+{m.kind === "escalation" ? m.granted : 0} kredit</code> dengan alasan tertulis, dikabulkan.</>,
    },
    early_stop: {
      title: "Berhenti dini",
      at: `langkah ${"step" in m ? m.step : ""}`,
      icon: <StopIcon />,
      desc: <>Berhenti lebih awal &amp; melewati probe sisa, band tak akan berubah.</>,
    },
    memory: {
      title: "Memori",
      at: "memori",
      icon: <MemoryIcon />,
      desc: <>Run sebelumnya (<code>{m.kind === "memory" ? m.ref : ""}</code>) memandu rencana, bukan mengulang dari nol.</>,
    },
  }[m.kind];

  return (
    <div className="moment">
      <span className="at mono">{view.at}</span>
      <div className="ic">{view.icon}</div>
      <div className="t">{view.title}</div>
      <div className="d">{view.desc}</div>
    </div>
  );
}

function AdaptiveIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M4 20V10M4 10l5-5 4 4 7-7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M15 2h5v5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function EscalationIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M12 3v18M5 10l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function StopIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <rect x="5" y="5" width="14" height="14" rx="2" /><path d="M9 12h6" strokeLinecap="round" />
    </svg>
  );
}
function MemoryIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M12 8v4l3 2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3.5 12a8.5 8.5 0 1 0 2.5-6" strokeLinecap="round" />
      <path d="M6 3v3.5H2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
