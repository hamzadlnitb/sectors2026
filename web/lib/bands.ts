// Maps the frozen transcript `band` enum to UI labels + style classes.
// Band labels are English (stock-desk convention); Indonesian kept as a subtitle
// only where the design calls for it.

export type Band = "normal" | "perhatian" | "waspada" | "sangat_waspada";

export type BandMeta = {
  /** English label shown in chips/gauges, e.g. "HIGH ALERT". */
  label: string;
  /** Indonesian label from the contract, e.g. "sangat waspada". */
  id: string;
  /** CSS modifier class: normal | watch | alert | high. */
  cls: "normal" | "watch" | "alert" | "high";
};

const BANDS: Record<Band, BandMeta> = {
  normal: { label: "NORMAL", id: "normal", cls: "normal" },
  perhatian: { label: "WATCH", id: "perhatian", cls: "watch" },
  waspada: { label: "ALERT", id: "waspada", cls: "alert" },
  sangat_waspada: { label: "HIGH ALERT", id: "sangat waspada", cls: "high" },
};

export function bandMeta(band: Band): BandMeta {
  return BANDS[band] ?? BANDS.normal;
}
