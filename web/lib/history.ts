import { readFileSync } from "fs";
import { join } from "path";
import type { Band } from "./bands";
import type { ProbeName } from "./transcript";

// Riwayat analisa agen per emiten — ditulis core/export/to_json.py dari runs/.
// Feed aktivitas menjawab "agen ngapain hari ini"; berkas ini menjawab apa yang
// BERUBAH sejak terakhir kali agen melihat emiten yang sama. Delta itulah satu-
// satunya tempat perilaku memori terlihat tanpa membuka dua transkrip sekaligus.

export interface TrailStep {
  probe: ProbeName;
  finding: "confirmed" | "refuted" | "inconclusive";
  credits: number;
  /** false = probe dibuka di luar rencana awal (perutean adaptif). */
  planned: boolean;
}

export interface HistoryRun {
  id: string;
  as_of: string;
  pantau_score: number;
  band: Band;
  confidence: number;
  steps: number;
  credits_total: number;
  savings_pct: number;
  moments: string[];
  narrative_source: "llm" | "template";
  /** Berapa dari enam komponen skor yang punya angka. Rendah = skor tipis. */
  components_used: number;
  components_total: number;
  headline: string;
  trail: TrailStep[];
  /** null pada kunjungan pertama — "belum pernah dilihat" ≠ "tidak berubah". */
  delta_score: number | null;
  delta_band: boolean | null;
}

export interface SymbolHistory {
  symbol: string;
  kunjungan: number;
  pertama: string;
  terakhir: string;
  skor_terakhir: number;
  band_terakhir: Band;
  skor_min: number;
  skor_maks: number;
  kredit_total: number;
  jejak: HistoryRun[];
}

export interface History {
  generated_at: string;
  symbols: SymbolHistory[];
}

export function loadHistory(): History {
  try {
    return JSON.parse(
      readFileSync(join(process.cwd(), "public", "data", "history.json"), "utf8")
    );
  } catch {
    return { generated_at: "", symbols: [] };
  }
}
