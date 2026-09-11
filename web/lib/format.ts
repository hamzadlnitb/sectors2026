const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

/** "2026-09-05" → "5 Sep 2026". */
export function fmtDate(isoDate: string): string {
  const [y, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[(m || 1) - 1]} ${y}`;
}

/** "2026-09-05T17:30:00+07:00" → "2026-09-05 17:30 WIB" (data is EOD WIB). */
export function fmtAsOf(iso: string): string {
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/);
  if (!m) return iso;
  return `${m[1]} ${m[2]}:${m[3]} WIB`;
}

/** Render source_params as compact "k=v · k=v". */
export function fmtParams(params: Record<string, unknown>): string {
  return Object.entries(params)
    .map(([k, v]) => `${k}=${v}`)
    .join(" · ");
}
