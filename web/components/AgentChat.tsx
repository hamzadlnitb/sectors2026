"use client";

import { useState } from "react";
import { bandMeta, type Band } from "@/lib/bands";
import type { EvidenceEntry, Moment, Step } from "@/lib/transcript";

// Chat walkthrough — "ngobrol sama agen" atas transkrip STATIS. Jawaban ditarik
// dari steps/evidence/moments (nol LLM, nol backend, nol saran finansial).
// UI-nya sama dengan yang nanti dipakai live-mode (tinggal ganti sumber jadi WS).

type Tool = { label: string; onClick: () => void };
type Answer = { trace: string[]; text: string; tools?: Tool[] };
type Msg = { role: "user"; text: string } | { role: "agent"; answer: Answer };

const MOMENT_LABEL: Record<string, string> = {
  adaptive: "perutean adaptif",
  escalation: "eskalasi",
  early_stop: "penghentian dini",
  memory: "memori",
};

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
}) {
  const b = bandMeta(band);

  function openEvidence(id: string) {
    const el = document.getElementById(`ev-${id}`) as HTMLDetailsElement | null;
    if (!el) return;
    el.open = true;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
  }
  function scrollTo(sel: string) {
    document.querySelector(sel)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const strongest = [...evidence].sort((x, y) => y.credits_spent - x.credits_spent)[0];
  const last = steps[steps.length - 1];
  const esc = moments.find((m) => m.kind === "escalation");
  const adaptive = moments.find((m) => m.kind === "adaptive");

  // Intent = pertanyaan preset + kata kunci untuk input bebas.
  const intents: { q: string; keys: string[]; build: () => Answer }[] = [
    {
      q: `Kenapa hasilnya ${b.label}?`,
      keys: ["kenapa", "band", "hasil", "skor", "score", "waspada", "normal", "alert"],
      build: () => {
        const confirmed = steps.filter((s) => s.finding === "confirmed");
        return {
          trace: ["baca skor & band", `tinjau ${confirmed.length} langkah terkonfirmasi`],
          text:
            `Skornya ${score}/100 → ${b.label} (keyakinan ${Math.round(confidence * 100)}%). ` +
            (confirmed.length
              ? `${confirmed.length} dari ${steps.length} langkah terkonfirmasi: ${confirmed
                  .map((s) => s.probe)
                  .join(", ")}. Tiap angkanya bisa ditelusuri ke buku bukti.`
              : `Tidak ada pola tidak biasa yang menonjol; agen berhenti dini.`),
          tools: strongest
            ? [{ label: `Buka bukti: ${strongest.label}`, onClick: () => openEvidence(strongest.id) }]
            : undefined,
        };
      },
    },
    {
      q: "Bukti apa yang paling menentukan?",
      keys: ["bukti", "evidence", "menentukan", "kuat", "terkuat"],
      build: () =>
        strongest
          ? {
              trace: ["buka buku bukti", "urutkan menurut biaya kredit"],
              text: `Bukti termahal (paling dalam) di investigasi ini: ${strongest.label} = ${strongest.display}, dari probe ${strongest.probe} (${strongest.credits_spent} kredit). Klik untuk lihat endpoint & as_of-nya.`,
              tools: [{ label: `Buka: ${strongest.label}`, onClick: () => openEvidence(strongest.id) }],
            }
          : { trace: ["cek buku bukti"], text: "Investigasi ini tidak mengumpulkan bukti berbayar." },
    },
    {
      q: "Kenapa agen berhenti & berapa hematnya?",
      keys: ["berhenti", "stop", "hemat", "kredit", "budget", "pagu"],
      build: () => ({
        trace: ["baca langkah terakhir", "bandingkan kredit vs baseline"],
        text:
          `Agen berhenti setelah ${steps.length} langkah — "${last?.reason ?? ""}" ` +
          `Total ${creditsTotal} kredit vs ${baseline} untuk investigasi menyeluruh → hemat ${savings}%.`,
        tools: [{ label: "Lihat di replay", onClick: () => scrollTo(".trail") }],
      }),
    },
    {
      q: "Apa momen agentiknya?",
      keys: ["momen", "agentik", "agentic", "adaptif", "adaptive"],
      build: () => ({
        trace: ["deteksi momen agentik"],
        text: moments.length
          ? `Terdeteksi: ${moments.map((m) => MOMENT_LABEL[m.kind]).join(", ")}. Ini yang membedakan agen dari if-else.`
          : "Investigasi ringkas — tidak ada momen agentik khusus selain penghentian dini.",
        tools: [{ label: "Lihat momen", onClick: () => scrollTo(".moments") }],
      }),
    },
    {
      q: "Ada eskalasi?",
      keys: ["eskalasi", "escalate", "tambah pagu"],
      build: () =>
        esc && esc.kind === "escalation"
          ? {
              trace: ["cari langkah eskalasi"],
              text: `Ya — pada langkah ${esc.step} agen minta tambah pagu +${esc.granted} kredit dengan alasan tertulis, dan dikabulkan.`,
              tools: [{ label: "Lihat di replay", onClick: () => scrollTo(".trail") }],
            }
          : { trace: ["cari langkah eskalasi"], text: "Tidak ada eskalasi — agen cukup dengan pagu awalnya." },
    },
    {
      q: adaptive ? "Kenapa buka probe di luar rencana?" : "Apa itu perutean adaptif?",
      keys: ["luar rencana", "adaptif", "adaptive", "routing", "perutean"],
      build: () =>
        adaptive && adaptive.kind === "adaptive"
          ? {
              trace: ["bandingkan probe vs rencana awal"],
              text: `Pada langkah ${adaptive.step} agen membuka \`${adaptive.probe}\` — tidak ada di rencana awal — karena temuan sebelumnya mengejutkan. Ini perutean adaptif.`,
              tools: [{ label: "Lihat di replay", onClick: () => scrollTo(".trail") }],
            }
          : { trace: ["cek rencana"], text: "Semua probe di investigasi ini sudah ada di rencana awal — tidak ada perutean adaptif." },
    },
  ];

  if (memoryRef) {
    intents.push({
      q: "Ini investigasi ulang?",
      keys: ["memori", "memory", "ulang", "sebelum"],
      build: () => ({
        trace: ["cek memori per-ticker"],
        text: `Ya — agen mengingat run sebelumnya (${memoryRef}) dan menyusun rencana berbeda diarahkan ke apa yang berubah.`,
      }),
    });
  }

  const greeting: Answer = {
    trace: [],
    text: `Aku bisa menjelaskan investigasi ${symbol} ini dari transkripnya — pilih pertanyaan atau ketik. Aku hanya menjawab dari bukti yang ada, dan ini bukan saran investasi.`,
  };
  const [log, setLog] = useState<Msg[]>([{ role: "agent", answer: greeting }]);
  const [input, setInput] = useState("");

  function ask(q: string) {
    const norm = q.toLowerCase();
    const hit =
      intents.find((it) => it.q.toLowerCase() === norm) ??
      intents.find((it) => it.keys.some((k) => norm.includes(k)));
    const answer: Answer = hit
      ? hit.build()
      : {
          trace: ["cari di transkrip"],
          text: "Aku cuma bisa menjawab dari transkrip investigasi ini. Coba salah satu pertanyaan di bawah.",
        };
    setLog((l) => [...l, { role: "user", text: q }, { role: "agent", answer }]);
  }

  return (
    <section className="agentchat">
      <div className="sec-label">
        <h2>Tanya agen</h2>
        <span className="n">{"//"} grounded ke transkrip · nol saran</span>
      </div>
      <div className="chat">
        <div className="chat-log">
          {log.map((m, i) =>
            m.role === "user" ? (
              <div className="cmsg user" key={i}>{m.text}</div>
            ) : (
              <div className="cmsg agent" key={i}>
                {m.answer.trace.length > 0 && (
                  <div className="ctrace">
                    {m.answer.trace.map((t, j) => (
                      <span className="tc" key={j}>▸ {t}</span>
                    ))}
                  </div>
                )}
                <div className="ctext">{m.answer.text}</div>
                {m.answer.tools && m.answer.tools.length > 0 && (
                  <div className="ctools">
                    {m.answer.tools.map((t, j) => (
                      <button key={j} onClick={t.onClick}>{t.label} →</button>
                    ))}
                  </div>
                )}
              </div>
            )
          )}
        </div>
        <div className="chat-chips">
          {intents.slice(0, 5).map((it) => (
            <button key={it.q} onClick={() => ask(it.q)}>{it.q}</button>
          ))}
        </div>
        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            const q = input.trim();
            if (q) { ask(q); setInput(""); }
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Tanya tentang ${symbol}…`}
            aria-label="Tanya agen"
          />
          <button type="submit">Kirim →</button>
        </form>
      </div>
    </section>
  );
}
