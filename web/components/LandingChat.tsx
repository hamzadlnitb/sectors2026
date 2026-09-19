"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ChatPanel from "@/components/ChatPanel";
import { bandMeta } from "@/lib/bands";
import { sourceForMode, type ChatAnswer, type Intent, type ToolRef } from "@/lib/chat";
import type { IndexEntry } from "@/lib/transcript";

// Landing chat — versi level-sistem dari "Tanya agen", widget mengambang. Menjawab
// soal hasil investigasi HARI INI (index.json) supaya agen kelihatan "bekerja".
// Nol LLM/backend, nol saran. Bentuk jawaban = §4 kontrak; live = ganti prop mode.

export default function LandingChat({ items, mode = "static" }: { items: IndexEntry[]; mode?: "static" | "live" }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const fabRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  // Buka → fokus ke input; Escape → tutup & kembalikan fokus ke tombol pemicu.
  useEffect(() => {
    if (!open) return;
    popRef.current?.querySelector("input")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); fabRef.current?.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  function resolveTool(ref: ToolRef): (() => void) | undefined {
    if (ref.kind === "route") return () => router.push(ref.id);
    return undefined;
  }

  const source = sourceForMode(mode, () => {
    const total = items.length;
    const ranked = [...items].sort((a, b) => b.pantau_score - a.pantau_score);
    const top = ranked[0];
    const flagged = ranked.filter((e) => e.band !== "normal");
    const esc = items.filter((e) => e.moments.includes("escalation"));
    const adapt = items.filter((e) => e.moments.includes("adaptive"));
    const avgSav = total ? Math.round(items.reduce((s, e) => s + e.savings_pct, 0) / total) : 0;
    const routeTo = (e: IndexEntry): ToolRef => ({ kind: "route", id: `/investigasi/${e.id}/` });

    const intents: Intent[] = [
      {
        q: "Apa yang agen temukan hari ini?",
        keys: ["hari ini", "temukan", "hasil", "ringkas", "apa yang"],
        answer: () => ({
          trace: ["baca hasil sapuan", `hitung ${total} investigasi`],
          text:
            `Hari ini agen menyapu pasar lalu menyelidiki ${total} saham secara mandiri. ` +
            (flagged.length ? `${flagged.length} masuk pantauan: ${flagged.map((e) => e.symbol).join(", ")}` : "tidak ada yang naik ke level pantauan — semua NORMAL") +
            (esc.length ? `. ${esc.length} sempat minta tambah pagu (eskalasi)` : "") + ".",
          tools: top ? [{ label: `Buka investigasi ${(flagged[0] ?? top).symbol}`, ref: routeTo(flagged[0] ?? top) }] : [],
        }),
      },
      {
        q: "Mana yang paling perlu diperhatikan?",
        keys: ["perlu diperhatikan", "paling", "menonjol", "waspada", "bahaya", "mana"],
        answer: (): ChatAnswer => {
          const it = flagged[0] ?? top;
          if (!it) return { trace: ["urutkan menurut skor"], text: "Belum ada investigasi untuk ditinjau hari ini.", tools: [] };
          const b = bandMeta(it.band);
          return {
            trace: ["urutkan menurut skor & band"],
            text: flagged.length
              ? `${it.symbol} paling menonjol — skor ${it.pantau_score}/100 (${b.label}), ${it.steps} langkah. ${it.headline}`
              : `Semua di level NORMAL — tidak ada yang perlu diwaspadai. Skor tertinggi ${it.symbol} (${it.pantau_score}/100).`,
            tools: [{ label: `Buka investigasi ${it.symbol}`, ref: routeTo(it) }],
          };
        },
      },
      {
        q: "Berapa hemat kreditnya?",
        keys: ["hemat", "kredit", "efisien", "biaya", "murah"],
        answer: () => ({
          trace: ["bandingkan kredit vs baseline 6-probe"],
          text: `Dengan hanya mengejar bukti yang perlu lalu berhenti, agen memakai rata-rata ~${avgSav}% lebih sedikit kredit dibanding investigasi menyeluruh (6 probe) — di ${total} kasus hari ini.`,
          tools: [],
        }),
      },
      {
        q: "Bagaimana cara agen bekerja?",
        keys: ["cara", "bekerja", "kerja", "gimana", "bagaimana", "proses"],
        answer: () => ({
          trace: ["jelaskan pipeline"],
          text: "Tiga langkah: DETECT (sapu sinyal Tier-1 tiap hari bursa) → INVESTIGATE (agen pilih bukti yang dikejar, uji hipotesis, berhenti saat cukup) → EXPLAIN (skor deterministik + narasi tersitasi, tiap angka bisa ditelusuri ke sumbernya). Ini alat informasi & analisis, bukan saran investasi.",
          tools: [],
        }),
      },
      {
        q: "Ada momen agentik?",
        keys: ["momen", "agentik", "agentic", "eskalasi", "adaptif", "adaptive"],
        answer: (): ChatAnswer => {
          if (esc.length || adapt.length) {
            const parts: string[] = [];
            if (esc.length) parts.push(`${esc.length} eskalasi (${esc.map((e) => e.symbol).join(", ")})`);
            if (adapt.length) parts.push(`${adapt.length} perutean adaptif (${adapt.map((e) => e.symbol).join(", ")})`);
            const it = esc[0] ?? adapt[0];
            return { trace: ["cari momen di semua run"], text: `Ya — ${parts.join(", ")}. Inilah yang membedakan agen dari if-else.`, tools: it ? [{ label: `Buka investigasi ${it.symbol}`, ref: routeTo(it) }] : [] };
          }
          return { trace: ["cari momen di semua run"], text: "Hari ini kebanyakan berakhir dengan penghentian dini — agen berhenti begitu bukti cukup dan tak menghabiskan pagu. Tak ada eskalasi/perutean di luar rencana.", tools: [] };
        },
      },
    ];

    const greeting: ChatAnswer = {
      trace: [],
      text: `Aku agen investigasi PANTAU. Tanya apa yang kutemukan hari ini — jawaban ditarik dari ${total} investigasi nyata. Ini bukan saran investasi.`,
      tools: [],
    };
    return { greeting, intents };
  });

  return (
    <>
      <button
        ref={fabRef}
        className={`chat-fab ${open ? "hide" : ""}`}
        onClick={() => setOpen(true)}
        aria-label="Buka chat — tanya agen"
        aria-expanded={open}
      >
        <span className="ping" />
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
          <path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 20l1.4-4.2A8.5 8.5 0 1 1 21 11.5z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Tanya agen
      </button>

      <div ref={popRef} className={`chat-pop ${open ? "open" : ""}`} role="dialog" aria-modal="false" aria-label="Chat — tanya agen" aria-hidden={!open} inert={!open}>
        <div className="chat-pop-head">
          <span className="ttl">Coba tanya agen <span className="n">{"//"} hasil hari ini</span></span>
          <button className="cx" onClick={() => setOpen(false)} aria-label="Tutup chat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <ChatPanel source={source} resolveTool={resolveTool} placeholder="Tanya soal hasil hari ini…" />
      </div>
    </>
  );
}
