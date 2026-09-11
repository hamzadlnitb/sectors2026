import { readFileSync, readdirSync } from "fs";
import { join } from "path";
import type { Band } from "./bands";

// TypeScript mirror of contracts/schemas.py::InvestigationTranscript (schema 1.0).
// Kept read-only — the web only ever consumes these.

export type Transport = "rest" | "mcp";
export type ProbeName =
  | "broker_concentration" | "volume_anomaly" | "price_fundamental"
  | "free_float" | "foreign_flow" | "structural";
export type ComponentCode = "BCI" | "VAS" | "PFD" | "FFS" | "FRD" | "SSS";

export interface EvidenceEntry {
  id: string;
  label: string;
  value: number | string | null;
  display: string;
  probe: ProbeName;
  source_endpoint: string;
  source_params: Record<string, unknown>;
  source_transport: Transport;
  as_of: string;
  credits_spent: number;
}

export interface Hypothesis {
  id: string;
  claim: string;
  probes: ProbeName[];
  priority: number;
}

export interface Step {
  step: number;
  hypothesis: string | null;
  probe: ProbeName;
  finding: "confirmed" | "refuted" | "inconclusive";
  next_action: "continue" | "escalate" | "conclude";
  new_probe: ProbeName | null;
  budget_granted: number;
  reason: string;
  credits_spent: number;
  credits_remaining: number;
}

export interface ComponentScore {
  code: ComponentCode;
  sub_score: number | null;
  weight: number;
  evidence_ids: string[];
  investigated: boolean;
}

export interface Transcript {
  schema_version: "1.0";
  symbol: string;
  as_of: string;
  weights_version: string;
  plan: { hypotheses: Hypothesis[]; credit_budget_requested: number; rationale: string };
  steps: Step[];
  evidence: EvidenceEntry[];
  components: ComponentScore[];
  pantau_score: number;
  band: Band;
  confidence: number;
  credits_total: number;
  baseline_credits: number;
  narrative: string;
  narrative_source: "llm" | "template";
  memory_ref: string | null;
  disclaimer: string;
}

const DATA_DIR = join(process.cwd(), "public", "data", "investigations");

/** All investigation ids (filename without .json), read at build time. */
export function listInvestigationIds(): string[] {
  try {
    return readdirSync(DATA_DIR)
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.replace(/\.json$/, ""))
      .sort();
  } catch {
    return [];
  }
}

export function loadInvestigation(id: string): Transcript {
  return JSON.parse(readFileSync(join(DATA_DIR, `${id}.json`), "utf8"));
}

// ── index.json — summaries emitted by core/export/to_json.py ─────────

export interface IndexEntry {
  id: string;
  symbol: string;
  as_of: string;
  pantau_score: number;
  band: Band;
  confidence: number;
  steps: number;
  credits_total: number;
  baseline_credits: number;
  savings_pct: number;
  memory_ref: string | null;
  narrative_source: "llm" | "template";
  moments: string[];
  headline: string;
}

export interface DataIndex {
  generated_at: string;
  investigations: IndexEntry[];
  watchlist_dates: { as_of: string; generated_at: string | null; credits_spent: number | null; candidates: number }[];
}

const EMPTY_INDEX: DataIndex = { generated_at: "", investigations: [], watchlist_dates: [] };

export function loadIndex(): DataIndex {
  try {
    return JSON.parse(readFileSync(join(process.cwd(), "public", "data", "index.json"), "utf8"));
  } catch {
    return EMPTY_INDEX;
  }
}

/** Latest investigation id per symbol — for routing a ticker search. */
export function symbolToId(index: DataIndex): Record<string, string> {
  const map: Record<string, string> = {};
  for (const e of index.investigations) {
    const prev = map[e.symbol];
    if (!prev || e.as_of > prev.split("-").slice(1).join("-")) map[e.symbol] = e.id;
  }
  return map;
}

// ── Derived views ────────────────────────────────────────────────────

export function savingsPct(t: Transcript): number {
  if (!t.baseline_credits) return 0;
  return Math.round((1 - t.credits_total / t.baseline_credits) * 100);
}

/** End-point of the gauge arc for a 0–100 score, on the semicircle
 *  centred at (140,150) r=120 used by the SVG. */
export function gaugeDot(score: number): { x: number; y: number } {
  const f = Math.max(0, Math.min(100, score)) / 100;
  const theta = ((180 - 180 * f) * Math.PI) / 180;
  return { x: 140 + 120 * Math.cos(theta), y: 150 - 120 * Math.sin(theta) };
}

export type Moment =
  | { kind: "adaptive"; step: number; probe: ProbeName }
  | { kind: "escalation"; step: number; granted: number }
  | { kind: "early_stop"; step: number }
  | { kind: "memory"; ref: string };

/** The four agentic behaviours Track 1 is judged on, read straight from the
 *  transcript so the UI never overstates what the agent actually did. */
export function detectMoments(t: Transcript): Moment[] {
  const planned = new Set<ProbeName>(t.plan.hypotheses.flatMap((h) => h.probes));
  const out: Moment[] = [];

  const adaptive = t.steps.find((s) => !planned.has(s.probe));
  if (adaptive) out.push({ kind: "adaptive", step: adaptive.step, probe: adaptive.probe });

  const esc = t.steps.find((s) => s.next_action === "escalate");
  if (esc) out.push({ kind: "escalation", step: esc.step, granted: esc.budget_granted });

  const last = t.steps[t.steps.length - 1];
  if (last && last.next_action === "conclude" && t.steps.length < 6 && t.credits_total < t.baseline_credits) {
    out.push({ kind: "early_stop", step: last.step });
  }

  if (t.memory_ref) out.push({ kind: "memory", ref: t.memory_ref });

  return out;
}
