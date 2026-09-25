const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const DOW_FULL = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
const p2 = (n: number) => String(n).padStart(2, "0");

/** "2026-09-05" → "5 Sep 2026". */
export function fmtDate(isoDate: string): string {
  const [y, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[(m || 1) - 1]} ${y}`;
}

/** Nama hari Indonesia dari tanggal ISO. "2026-09-18" → "Jumat". */
export function weekdayId(isoDate: string): string {
  const [y, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  return DOW_FULL[new Date(Date.UTC(y, (m || 1) - 1, d || 1)).getUTCDay()];
}

/** true kalau tanggal jatuh di akhir pekan (bursa tutup). */
export function isWeekend(isoDate: string): boolean {
  const [y, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  const dow = new Date(Date.UTC(y, (m || 1) - 1, d || 1)).getUTCDay();
  return dow === 0 || dow === 6;
}

/** Konversi timestamp ISO (offset apa pun) → jam WIB. "…T14:35:00+00:00" → "21:35 WIB". */
export function wibTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const w = new Date(t + 7 * 3600 * 1000); // WIB = UTC+7, baca field UTC
  return `${p2(w.getUTCHours())}:${p2(w.getUTCMinutes())} WIB`;
}

/** "2026-09-05T17:30:00+07:00" → "5 Sep 2026 · 17:30 WIB" (data EOD, jujur soal jam). */
export function fmtAsOf(iso: string): string {
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/);
  if (!m) return iso;
  return `${m[1]} ${m[2]}:${m[3]} WIB`;
}

/** Angka rupiah → "Rp 47,0 M" / "Rp 1,2 T" (ringkas, gaya Indonesia). Untuk nilai
 *  mentah bila kelak web perlu memformat sendiri; data transkrip sudah pra-format. */
export function fmtIDR(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? "−" : "";
  const scale = (v: number) => v.toFixed(1).replace(".", ",").replace(",0", "");
  if (abs >= 1e12) return `${sign}Rp ${scale(abs / 1e12)} T`;
  if (abs >= 1e9) return `${sign}Rp ${scale(abs / 1e9)} M`;
  if (abs >= 1e6) return `${sign}Rp ${scale(abs / 1e6)} jt`;
  return `${sign}Rp ${Math.round(abs).toLocaleString("id-ID")}`;
}

/** Label hemat kredit yang aman untuk nilai negatif. Sejak C6 (Hamzah),
 *  `savings_pct` boleh < 0 = agen memakai LEBIH banyak kredit dari baseline
 *  menyeluruh (agen kalah — dan itu jujur, tak disembunyikan). */
export function fmtSavings(pct: number): { text: string; sign: "good" | "bad" | "flat" } {
  if (pct > 0) return { text: `hemat ${pct}%`, sign: "good" };
  if (pct < 0) return { text: `${-pct}% lebih boros`, sign: "bad" };
  return { text: "setara baseline", sign: "flat" };
}

/** Render source_params as compact "k=v · k=v". */
export function fmtParams(params: Record<string, unknown>): string {
  return Object.entries(params)
    .map(([k, v]) => `${k}=${v}`)
    .join(" · ");
}
