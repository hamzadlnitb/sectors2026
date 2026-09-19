"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { bandMeta } from "@/lib/bands";
import type { IndexEntry } from "@/lib/transcript";

// Landing chat — versi level-sistem dari "Tanya agen". Menjawab tentang hasil
// investigasi HARI INI (dari index.json) supaya pengunjung langsung lihat agen
// "bekerja". Nol LLM, nol backend, nol saran finansial. UI sama dengan AgentChat
// (kelak tinggal ganti sumber jadi WS untuk live-mode).

type Tool = { label: string; go: string };
type Answer = { trace: string[]; text: string; tools?: Tool[] };
type Msg = { role: "user"; text: string } | { role: "agent"; answer: Answer };

export default function LandingChat({ items }: { items: IndexEntry[] }) {
  const router = useRouter();
  const total = items.length;
  const ranked = [...items].sort((a, b) => b.pantau_score - a.pantau_score);
  const top = ranked[0];
  const flagged = ranked.filter((e) => e.band !== "normal");
  const esc = items.filter((e) => e.moments.includes("escalation"));
  const adapt = items.filter((e) => e.moments.includes("adaptive"));
  const avgSav = total ? Math.round(items.reduce((s, e) => s + e.savings_pct, 0) / total) : 0;
  const openTool = (e: IndexEntry): Tool => ({ label: `Buka investigasi ${e.symbol}`, go: `/investigasi/${e.id}/` });

  const intents: { q: string; keys: string[]; build: () => Answer }[] = [
    {
      q: "Apa yang agen temukan hari ini?",
      keys: ["hari ini", "temukan", "hasil", "ringkas", "apa yang"],
      build: () => ({
        trace: ["baca hasil sapuan", `hitung ${total} investigasi`],
        text:
          `Hari ini agen menyapu pasar lalu menyelidiki ${total} saham secara mandiri. ` +
          (flagged.length
            ? `${flagged.length} masuk pantauan: ${flagged.map((e) => e.symbol).join(", ")}`
            : "tidak ada yang naik ke level pantauan — semua NORMAL") +
          (esc.length ? `. ${esc.length} sempat minta tambah pagu (eskalasi)` : "") + ".",
        tools: top ? [openTool(flagged[0] ?? top)] : undefined,
      }),
    },
    {
      q: "Mana yang paling perlu diperhatikan?",
      keys: ["perlu diperhatikan", "paling", "menonjol", "waspada", "bahaya", "mana"],
      build: () => {
        const it = flagged[0] ?? top;
        if (!it) return { trace: ["urutkan menurut skor"], text: "Belum ada investigasi untuk ditinjau hari ini." };
        const b = bandMeta(it.band);
        return {
          trace: ["urutkan menurut skor & band"],
          text: flagged.length
            ? `${it.symbol} paling menonjol — skor ${it.pantau_score}/100 (${b.label}), ${it.steps} langkah. ${it.headline}`
            : `Semua di level NORMAL — tidak ada yang perlu diwaspadai. Skor tertinggi ${it.symbol} (${it.pantau_score}/100).`,
          tools: [openTool(it)],
        };
      },
    },
    {
      q: "Berapa hemat kreditnya?",
      keys: ["hemat", "kredit", "efisien", "biaya", "murah"],
      build: () => ({
        trace: ["bandingkan kredit vs baseline 6-probe"],
        text: `Dengan hanya mengejar bukti yang perlu lalu berhenti, agen memakai rata-rata ~${avgSav}% lebih sedikit kredit dibanding investigasi menyeluruh (6 probe) — di ${total} kasus hari ini.`,
      }),
    },
    {
      q: "Bagaimana cara agen bekerja?",
      keys: ["cara", "bekerja", "kerja", "gimana", "bagaimana", "proses"],
      build: () => ({
        trace: ["jelaskan pipeline"],
        text: "Tiga langkah: DETECT (sapu sinyal Tier-1 tiap hari bursa) → INVESTIGATE (agen pilih bukti yang dikejar, uji hipotesis, berhenti saat cukup) → EXPLAIN (skor deterministik + narasi tersitasi, tiap angka bisa ditelusuri ke sumbernya). Ini alat informasi & analisis, bukan saran investasi.",
      }),
    },
    {
      q: "Ada momen agentik?",
      keys: ["momen", "agentik", "agentic", "eskalasi", "adaptif", "adaptive"],
      build: () => {
        if (esc.length || adapt.length) {
          const parts: string[] = [];
          if (esc.length) parts.push(`${esc.length} eskalasi (${esc.map((e) => e.symbol).join(", ")})`);
          if (adapt.length) parts.push(`${adapt.length} perutean adaptif (${adapt.map((e) => e.symbol).join(", ")})`);
          const it = esc[0] ?? adapt[0];
          return { trace: ["cari momen di semua run"], text: `Ya — ${parts.join(", ")}. Inilah yang membedakan agen dari if-else.`, tools: it ? [openTool(it)] : undefined };
        }
        return { trace: ["cari momen di semua run"], text: "Hari ini kebanyakan berakhir dengan penghentian dini — agen berhenti begitu bukti cukup dan tak menghabiskan pagu. Tak ada eskalasi/perutean di luar rencana." };
      },
    },
  ];

  const greeting: Answer = {
    trace: [],
    text: `Aku agen investigasi PANTAU. Tanya apa yang kutemukan hari ini — jawaban ditarik dari ${total} investigasi nyata. Ini bukan saran investasi.`,
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
      : { trace: ["cari di hasil hari ini"], text: "Aku menjawab dari investigasi hari ini. Coba salah satu pertanyaan di bawah." };
    setLog((l) => [...l, { role: "user", text: q }, { role: "agent", answer }]);
  }

  return (
    <section className="agentchat">
      <div className="sec-label">
        <h2>Coba tanya agen</h2>
        <span className="n">{"//"} jawaban dari investigasi hari ini · nol saran</span>
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
                      <button key={j} onClick={() => router.push(t.go)}>{t.label} →</button>
                    ))}
                  </div>
                )}
              </div>
            )
          )}
        </div>
        <div className="chat-chips">
          {intents.map((it) => (
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
            placeholder="Tanya soal hasil hari ini…"
            aria-label="Tanya agen"
          />
          <button type="submit">Kirim →</button>
        </form>
      </div>
    </section>
  );
}
