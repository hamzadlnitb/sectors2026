"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ChatPanel from "@/components/ChatPanel";
import { bandMeta } from "@/lib/bands";
import { sourceForMode, type ChatAnswer, type Intent, type ToolRef } from "@/lib/chat";
import { fmtDate } from "@/lib/format";
import type { IndexEntry } from "@/lib/transcript";

// Landing chat, versi level-sistem dari "Tanya agen", widget mengambang. Menjawab
// soal hasil investigasi HARI INI (index.json) supaya agen kelihatan "bekerja".
// Nol LLM/backend, nol saran. Bentuk jawaban = §4 kontrak; live = ganti prop mode.

export default function LandingChat({ items, mode = "static" }: { items: IndexEntry[]; mode?: "static" | "live" }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [session, setSession] = useState(0); // ganti tiap buka → ChatPanel remount, saran pertanyaan muncul lagi
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
    const mem = items.filter((e) => e.moments.includes("memory"));
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
            (flagged.length ? `${flagged.length} masuk pantauan: ${flagged.map((e) => e.symbol).join(", ")}` : "tidak ada yang naik ke level pantauan, semua NORMAL") +
            (esc.length ? `. ${esc.length} sempat minta tambah jatah (eskalasi)` : "") + ".",
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
              ? `${it.symbol} paling menonjol, skor ${it.pantau_score}/100 (${b.label}), ${it.steps} langkah. ${it.headline}`
              : `Semua di level NORMAL, tidak ada yang perlu diwaspadai. Skor tertinggi ${it.symbol} (${it.pantau_score}/100).`,
            tools: [{ label: `Buka investigasi ${it.symbol}`, ref: routeTo(it) }],
          };
        },
      },
      {
        q: "Berapa hemat kreditnya?",
        keys: ["hemat", "kredit", "efisien", "biaya", "murah"],
        answer: () => ({
          trace: ["bandingkan kredit vs baseline 6-probe"],
          text: `Dengan hanya mengejar bukti yang perlu lalu berhenti, agen memakai rata-rata ${avgSav >= 0 ? `~${avgSav}% lebih sedikit` : `~${-avgSav}% lebih banyak`} kredit dibanding investigasi menyeluruh (6 probe), di ${total} kasus hari ini.`,
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
          const parts: string[] = [];
          if (esc.length) parts.push(`${esc.length} minta tambah jatah (${esc.map((e) => e.symbol).join(", ")})`);
          if (adapt.length) parts.push(`${adapt.length} keluar dari rencana (${adapt.map((e) => e.symbol).join(", ")})`);
          if (mem.length) parts.push(`${mem.length} investigasi ulang dengan memori (${mem.map((e) => e.symbol).join(", ")})`);
          if (parts.length) {
            const it = esc[0] ?? adapt[0] ?? mem[0];
            return { trace: ["cari momen di semua run"], text: `Ya, ${parts.join("; ")}. Inilah yang bikin agen terasa seperti analis, bukan rumus.`, tools: it ? [{ label: `Buka investigasi ${it.symbol}`, ref: routeTo(it) }] : [] };
          }
          return { trace: ["cari momen di semua run"], text: "Hari ini kebanyakan berakhir dengan agen berhenti lebih awal begitu bukti cukup, tanpa menghabiskan jatah. Tak ada yang minta tambah jatah atau keluar dari rencana.", tools: [] };
        },
      },
    ];

    if (mem.length) {
      intents.push({
        q: "Ada investigasi ulang?",
        keys: ["ulang", "memori", "memory", "sebelumnya", "ingat"],
        answer: (): ChatAnswer => ({
          trace: ["cari momen memori"],
          text: `Ya, ${mem.map((e) => e.symbol).join(", ")} diselidiki ulang. Agen mengingat run sebelumnya dan menyusun rencana berbeda, diarahkan ke apa yang berubah, bukan mengulang dari nol.`,
          tools: [{ label: `Buka investigasi ${mem[0].symbol}`, ref: routeTo(mem[0]) }],
        }),
      });
    }

    // Kenali nama emiten yang ADA di data: ketik "jawa" → hasil terbaru + tombol buka.
    // Ditambahkan setelah pertanyaan utama, jadi tidak muncul sebagai chip (chip dibatasi 4).
    const symbols = [...new Set(items.map((e) => e.symbol))].sort();
    for (const sym of symbols) {
      intents.push({
        q: sym,
        keys: [sym.toLowerCase()],
        answer: (): ChatAnswer => {
          const runs = items
            .filter((e) => e.symbol === sym)
            .sort((a, b) => b.as_of.localeCompare(a.as_of));
          const it = runs[0];
          const b = bandMeta(it.band);
          return {
            trace: [`cari emiten ${sym}`, "ambil investigasi terbaru"],
            text:
              `${sym}: investigasi terakhir ${fmtDate(it.as_of)} → skor ${it.pantau_score}/100 (${b.label}), ` +
              `keyakinan ${Math.round(it.confidence * 100)}%, ${it.steps} langkah.` +
              (runs.length > 1 ? ` Ada ${runs.length} investigasi untuk ${sym}, lihat perubahannya di Riwayat.` : "") +
              " Ini bukan saran investasi.",
            tools: [
              { label: `Buka investigasi ${sym}`, ref: routeTo(it) },
              ...(runs.length > 1
                ? [{ label: "Lihat riwayat", ref: { kind: "route", id: "/riwayat" } as ToolRef }]
                : []),
            ],
          };
        },
      });
    }

    const greeting: ChatAnswer = {
      trace: [],
      text: `Aku agen investigasi PANTAU. Tanya apa yang kutemukan hari ini, jawaban ditarik dari ${total} investigasi nyata.`,
      tools: [],
    };
    // Fallback ikut menyebut emiten yang tersedia, jadi jujur saat kode tak dikenal.
    const fallback: ChatAnswer = {
      trace: ["cari di data yang ada"],
      text: `Aku menjawab dari data yang ada. Untuk cek satu emiten, ketik kodenya, yang tersedia: ${symbols.join(", ")}. Atau pilih pertanyaan di bawah.`,
      tools: [],
    };
    return { greeting, intents, fallback };
  });

  return (
    <>
      <button
        ref={fabRef}
        className={`chat-fab ${open ? "hide" : ""}`}
        onClick={() => { setSession((s) => s + 1); setOpen(true); }}
        aria-label="Buka chat, tanya agen"
        aria-expanded={open}
      >
        <span className="ping" />
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
          <path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 20l1.4-4.2A8.5 8.5 0 1 1 21 11.5z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Tanya agen
      </button>

      <div ref={popRef} className={`chat-pop ${open ? "open" : ""}`} role="dialog" aria-modal="false" aria-label="Chat, tanya agen" aria-hidden={!open} inert={!open}>
        <div className="chat-pop-head">
          <span className="cha" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
              <path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 20l1.4-4.2A8.5 8.5 0 1 1 21 11.5z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="ttl">Tanya agen PANTAU<span className="n">hasil hari ini</span></span>
          <button className="cx" onClick={() => setOpen(false)} aria-label="Tutup chat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <ChatPanel key={session} source={source} resolveTool={resolveTool} placeholder="Tanya soal hasil hari ini…" />
        <div className="chat-pop-foot">Jawaban dari data tersimpan · bukan saran investasi</div>
      </div>
    </>
  );
}
