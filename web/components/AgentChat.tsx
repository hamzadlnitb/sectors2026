"use client";

import ChatPanel from "@/components/ChatPanel";
import { bandMeta, type Band } from "@/lib/bands";
import { sourceForMode, type ChatAnswer, type Intent, type ToolRef } from "@/lib/chat";
import type { EvidenceEntry, Moment, Step } from "@/lib/transcript";

// Chat walkthrough — "ngobrol sama agen" atas transkrip STATIS. Jawaban ditarik
// dari steps/evidence/moments (nol LLM, nol backend, nol saran finansial).
// Bentuk jawaban = §4 kontrak middleware; live-mode = ganti prop mode saja.

const MOMENT_LABEL: Record<string, string> = {
  adaptive: "perutean adaptif",
  escalation: "eskalasi",
  early_stop: "penghentian dini",
  memory: "memori",
};

// Aksi tool di halaman detail: buka bukti (ev-<id>) & scroll ke bagian.
function openEvidence(id: string) {
  const el = document.getElementById(`ev-${id}`) as HTMLDetailsElement | null;
  if (!el) return;
  el.open = true;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("flash");
  void el.offsetWidth;
  el.classList.add("flash");
}
function resolveTool(ref: ToolRef): (() => void) | undefined {
  if (ref.kind === "evidence") return () => openEvidence(ref.id);
  if (ref.kind === "section") return () => document.querySelector(ref.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  return undefined;
}

export default function AgentChat({
  symbol,
  band,
  score,
  confidence,
  creditsTotal,
  baseline,
  savings,
  steps,
  evidence,
  moments,
  memoryRef,
  mode = "static",
}: {
  symbol: string;
  band: Band;
  score: number;
  confidence: number;
  creditsTotal: number;
  baseline: number;
  savings: number;
  steps: Step[];
  evidence: EvidenceEntry[];
  moments: Moment[];
  memoryRef: string | null;
  mode?: "static" | "live";
}) {
  const source = sourceForMode(mode, () => {
    const b = bandMeta(band);
    const strongest = [...evidence].sort((x, y) => y.credits_spent - x.credits_spent)[0];
    const last = steps[steps.length - 1];
    const esc = moments.find((m) => m.kind === "escalation");
    const adaptive = moments.find((m) => m.kind === "adaptive");
    const ev = (id: string): ToolRef => ({ kind: "evidence", id });
    const sec = (id: string): ToolRef => ({ kind: "section", id });

    const intents: Intent[] = [
      {
        q: `Kenapa hasilnya ${b.label}?`,
        keys: ["kenapa", "band", "hasil", "skor", "score", "waspada", "normal", "alert"],
        answer: () => {
          const confirmed = steps.filter((s) => s.finding === "confirmed");
          return {
            trace: ["baca skor & band", `tinjau ${confirmed.length} langkah terkonfirmasi`],
            text:
              `Skornya ${score}/100 → ${b.label} (keyakinan ${Math.round(confidence * 100)}%). ` +
              (confirmed.length
                ? `${confirmed.length} dari ${steps.length} langkah terkonfirmasi: ${confirmed.map((s) => s.probe).join(", ")}. Tiap angkanya bisa ditelusuri ke buku bukti.`
                : `Tidak ada pola tidak biasa yang menonjol; agen berhenti dini.`),
            tools: strongest ? [{ label: `Buka bukti: ${strongest.label}`, ref: ev(strongest.id) }] : [],
          };
        },
      },
      {
        q: "Bukti apa yang paling menentukan?",
        keys: ["bukti", "evidence", "menentukan", "kuat", "terkuat"],
        answer: (): ChatAnswer =>
          strongest
            ? {
                trace: ["buka buku bukti", "urutkan menurut biaya kredit"],
                text: `Bukti termahal (paling dalam) di investigasi ini: ${strongest.label} = ${strongest.display}, dari probe ${strongest.probe} (${strongest.credits_spent} kredit). Klik untuk lihat endpoint & as_of-nya.`,
                tools: [{ label: `Buka: ${strongest.label}`, ref: ev(strongest.id) }],
              }
            : { trace: ["cek buku bukti"], text: "Investigasi ini tidak mengumpulkan bukti berbayar.", tools: [] },
      },
      {
        q: "Kenapa agen berhenti & berapa hematnya?",
        keys: ["berhenti", "stop", "hemat", "kredit", "budget", "pagu"],
        answer: () => ({
          trace: ["baca langkah terakhir", "bandingkan kredit vs baseline"],
          text: `Agen berhenti setelah ${steps.length} langkah — "${last?.reason ?? ""}" Total ${creditsTotal} kredit vs ${baseline} untuk investigasi menyeluruh → hemat ${savings}%.`,
          tools: [{ label: "Lihat di replay", ref: sec(".trail") }],
        }),
      },
      {
        q: "Apa momen agentiknya?",
        keys: ["momen", "agentik", "agentic", "adaptif", "adaptive"],
        answer: () => ({
          trace: ["deteksi momen agentik"],
          text: moments.length
            ? `Terdeteksi: ${moments.map((m) => MOMENT_LABEL[m.kind]).join(", ")}. Ini yang membedakan agen dari if-else.`
            : "Investigasi ringkas — tidak ada momen agentik khusus selain penghentian dini.",
          tools: [{ label: "Lihat momen", ref: sec(".moments") }],
        }),
      },
      {
        q: "Ada eskalasi?",
        keys: ["eskalasi", "escalate", "tambah pagu"],
        answer: (): ChatAnswer =>
          esc && esc.kind === "escalation"
            ? {
                trace: ["cari langkah eskalasi"],
                text: `Ya — pada langkah ${esc.step} agen minta tambah pagu +${esc.granted} kredit dengan alasan tertulis, dan dikabulkan.`,
                tools: [{ label: "Lihat di replay", ref: sec(".trail") }],
              }
            : { trace: ["cari langkah eskalasi"], text: "Tidak ada eskalasi — agen cukup dengan pagu awalnya.", tools: [] },
      },
      {
        q: adaptive ? "Kenapa buka probe di luar rencana?" : "Apa itu perutean adaptif?",
        keys: ["luar rencana", "adaptif", "adaptive", "routing", "perutean"],
        answer: (): ChatAnswer =>
          adaptive && adaptive.kind === "adaptive"
            ? {
                trace: ["bandingkan probe vs rencana awal"],
                text: `Pada langkah ${adaptive.step} agen membuka \`${adaptive.probe}\` — tidak ada di rencana awal — karena temuan sebelumnya mengejutkan. Ini perutean adaptif.`,
                tools: [{ label: "Lihat di replay", ref: sec(".trail") }],
              }
            : { trace: ["cek rencana"], text: "Semua probe di investigasi ini sudah ada di rencana awal — tidak ada perutean adaptif.", tools: [] },
      },
    ];

    if (memoryRef) {
      intents.push({
        q: "Ini investigasi ulang?",
        keys: ["memori", "memory", "ulang", "sebelum"],
        answer: () => ({
          trace: ["cek memori per-ticker"],
          text: `Ya — agen mengingat run sebelumnya (${memoryRef}) dan menyusun rencana berbeda diarahkan ke apa yang berubah.`,
          tools: [],
        }),
      });
    }

    const greeting: ChatAnswer = {
      trace: [],
      text: `Aku bisa menjelaskan investigasi ${symbol} ini dari transkripnya — pilih pertanyaan atau ketik. Aku hanya menjawab dari bukti yang ada, dan ini bukan saran investasi.`,
      tools: [],
    };
    return { greeting, intents };
  });

  return (
    <section className="agentchat">
      <div className="sec-label">
        <h2>Tanya agen</h2>
        <span className="n">jawaban dari transkrip · bukan saran</span>
      </div>
      <ChatPanel source={source} resolveTool={resolveTool} placeholder={`Tanya tentang ${symbol}…`} />
    </section>
  );
}
