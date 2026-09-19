import { readFileSync } from "fs";
import { join } from "path";
import type { Band } from "./bands";

// Feed aktivitas agen (dashboard #4) — ditulis core/export/to_json.py dari runs/.
// Statis: alur agen-harian → berkas → frontend (analog "middleware" mode statis).

export interface ActivityEvent {
  ts: string;
  date: string;
  kind: "sweep" | "investigation";
  // sweep
  candidates?: number;
  credits?: number | null;
  // investigation
  id?: string;
  symbol?: string;
  band?: Band;
  pantau_score?: number;
  steps?: number;
  savings_pct?: number;
  moments?: string[];
}

export interface ActivityFeed {
  generated_at: string;
  events: ActivityEvent[];
}

export function loadActivity(): ActivityFeed {
  try {
    return JSON.parse(readFileSync(join(process.cwd(), "public", "data", "activity.json"), "utf8"));
  } catch {
    return { generated_at: "", events: [] };
  }
}
