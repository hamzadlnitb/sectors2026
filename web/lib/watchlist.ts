import { readFileSync } from "fs";
import { join } from "path";

// Watchlist arsip run otonom (cron), diekspor oleh core/export/to_json.py dari
// runs/<tgl>/watchlist.json. Skor kandidat = skor SELEKSI Tier-1 (0–1), bukan
// skor PANTAU — ambang untuk memutuskan siapa yang layak diselidiki.

export interface CandidateSignals {
  return_5d?: number;
  return_20d?: number;
  volume_z?: number;
  small_cap?: number;
  peristiwa?: number;
}

export interface Candidate {
  symbol: string;
  score: number;
  signals: CandidateSignals;
  alasan: string;
}

export interface Watchlist {
  as_of: string;
  generated_at?: string | null;
  credits_spent?: number | null;
  candidates: Candidate[];
}

export interface WatchDate {
  as_of: string;
  generated_at: string | null;
  credits_spent: number | null;
  candidates: number;
}

const WATCH_DIR = join(process.cwd(), "public", "data", "watchlist");

export function loadWatchlistDates(): WatchDate[] {
  try {
    const idx = JSON.parse(readFileSync(join(WATCH_DIR, "index.json"), "utf8"));
    return (idx.dates ?? []) as WatchDate[];
  } catch {
    return [];
  }
}

export function loadWatchlist(date: string): Watchlist | null {
  try {
    return JSON.parse(readFileSync(join(WATCH_DIR, `${date}.json`), "utf8"));
  } catch {
    return null;
  }
}
