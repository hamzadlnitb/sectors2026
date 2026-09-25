// Kontrak chat bersama untuk walkthrough statis + (nanti) live-mode.
// Bentuk `ChatAnswer` = persis §4 docs/MIDDLEWARE_CONTRACT.md: sumber live merakit
// Answer yang SAMA dari aliran WS, jadi komponen tak perlu ditulis ulang (drop-in).
// Client-safe: NOL impor fs (jangan impor lib/transcript di sini).

/** Referensi tool — dipetakan host ke aksi DOM/navigasi (lihat resolveTool). */
export type ToolRef =
  | { kind: "evidence"; id: string } // buka <details id="ev-<id>"> di halaman
  | { kind: "section"; id: string } // scroll ke selector CSS (mis. ".trail")
  | { kind: "route"; id: string }; // navigasi ke path (mis. "/investigasi/…")

export type ChatTool = { label: string; ref: ToolRef };
export type ChatAnswer = { trace: string[]; text: string; tools: ChatTool[] };
export type ChatMsg =
  | { role: "user"; text: string }
  | { role: "agent"; answer: ChatAnswer; streaming?: boolean };

/** Satu potongan aliran jawaban. Statis meng-yield trace→text→tools; live akan
 *  meng-yield banyak `{text}` (token demi token) — konsumen menyambungnya sama saja. */
export type ChatPatch = { trace?: string; text?: string; tool?: ChatTool };

export interface ChatSource {
  greeting: ChatAnswer;
  chips: string[];
  ask(q: string): AsyncGenerator<ChatPatch, void, unknown>;
}

/** Intent deterministik: pertanyaan preset + kata kunci untuk input bebas. */
export type Intent = { q: string; keys: string[]; answer: () => ChatAnswer };

export function matchIntent(intents: Intent[], q: string): Intent | undefined {
  const norm = q.toLowerCase();
  return (
    intents.find((it) => it.q.toLowerCase() === norm) ??
    intents.find((it) => it.keys.some((k) => norm.includes(k)))
  );
}

const DEFAULT_FALLBACK: ChatAnswer = {
  trace: ["cari di data yang ada"],
  text: "Aku cuma bisa menjawab dari data investigasi ini. Coba salah satu pertanyaan di bawah.",
  tools: [],
};

/** Sumber STATIS — jawaban ditarik dari transkrip/index (nol backend). Meng-yield
 *  dalam bentuk yang sama dengan sumber live agar jalur konsumsinya identik. */
export function staticSource(opts: {
  greeting: ChatAnswer;
  intents: Intent[];
  fallback?: ChatAnswer;
}): ChatSource {
  const { greeting, intents } = opts;
  const fallback = opts.fallback ?? DEFAULT_FALLBACK;
  return {
    greeting,
    chips: intents.map((it) => it.q),
    async *ask(q: string) {
      const hit = matchIntent(intents, q);
      const ans = hit ? hit.answer() : fallback;
      for (const t of ans.trace) yield { trace: t };
      if (ans.text) yield { text: ans.text };
      for (const tool of ans.tools) yield { tool };
    },
  };
}

/** Placeholder sumber LIVE. Fase B: ganti isinya dengan `liveSource(ws)` yang
 *  memetakan event WS (§8 kontrak) ke ChatPatch — komponen tak berubah.
 *  Sampai C6 disetujui & middleware ada, memilih mode "live" jujur bilang belum aktif. */
export function livePendingSource(greeting: ChatAnswer): ChatSource {
  return {
    greeting: {
      ...greeting,
      text: "Mode live belum aktif — menunggu middleware & persetujuan C6. Sementara ini jawaban ditarik dari transkrip statis.",
    },
    chips: [],
    async *ask() {
      /* belum ada aliran WS — Fase B mengganti ini dengan pemetaan event §8 */
    },
  };
}

/** Pilih sumber sesuai mode. Live-mode = satu baris ganti di sini nanti. */
export function sourceForMode(
  mode: "static" | "live",
  build: () => { greeting: ChatAnswer; intents: Intent[]; fallback?: ChatAnswer },
): ChatSource {
  const cfg = build();
  return mode === "live" ? livePendingSource(cfg.greeting) : staticSource(cfg);
}
