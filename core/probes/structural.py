"""SSS — Structural Signal Score.

Pertanyaan: **pernah disuspend? insider menjual? rights issue beruntun?**

Berbeda dari lima probe lain, ini bukan pengukuran melainkan penjumlahan
peristiwa berbobot. Tidak adanya peristiwa adalah temuan yang sah — skor 0
berarti "diperiksa, bersih", bukan "gagal mengukur".

Karena itu ada pembedaan yang penting: **tidak ada peristiwa untuk ticker ini**
menghasilkan skor 0 dengan bukti; **tabel peristiwa kosong sama sekali di
warehouse** menghasilkan unavailable, karena yang kita lihat bukan emiten yang
bersih melainkan warehouse yang belum diisi.
"""

from __future__ import annotations

import pandas as pd

from core.probes.base import BaseProbe, Context, Finding

SUSPENSI_BULAN = 24
FILING_HARI = 90
AKSI_BULAN = 24

# Bobot peristiwa. Dijumlahkan lalu dipotong di 100.
POIN_SUSPENSI = 40
POIN_SUSPENSI_TIDAK_WAJAR = 15   # tambahan kalau alasannya soal pergerakan harga
POIN_INSIDER_JUAL = 10
CAP_INSIDER = 30
POIN_RIGHTS_ISSUE = 12
CAP_AKSI = 25

# Kata kunci alasan suspensi yang menandakan pergerakan/aktivitas tidak wajar.
# Sumber label kalibrasi Hamzah memakai penyaringan serupa — kalau daftar ini
# berubah, kabari dia, karena himpunan positifnya ikut bergeser.
ALASAN_TIDAK_WAJAR = (
    "tidak wajar", "di luar kebiasaan", "unusual", "unusual market activity",
    "uma", "pergerakan harga", "peningkatan harga", "aktivitas transaksi",
)

AKSI_BERISIKO = ("rights_issue", "rights issue", "private_placement", "private placement",
                 "reverse_stock", "reverse stock")


def _bulan_lalu(as_of, bulan: int):
    tahun = as_of.year - (bulan // 12)
    bulan_sisa = as_of.month - (bulan % 12)
    if bulan_sisa <= 0:
        bulan_sisa += 12
        tahun -= 1
    return as_of.replace(year=tahun, month=bulan_sisa, day=min(as_of.day, 28))


class StructuralProbe(BaseProbe):
    name = "structural"
    component = "SSS"
    endpoints = ("fetch-suspensions", "fetch-filings", "fetch-corporate-actions")

    def _compute(self, symbol: str, ctx: Context) -> Finding:
        sejak_suspensi = _bulan_lalu(ctx.as_of, SUSPENSI_BULAN)
        sejak_aksi = _bulan_lalu(ctx.as_of, AKSI_BULAN)
        sejak_filing = ctx.as_of - pd.Timedelta(days=FILING_HARI).to_pytimedelta()

        ctx.ensure("suspensions", "fetch-suspensions",
                   {"symbol": symbol, "start": sejak_suspensi.isoformat(),
                    "end": ctx.as_of.isoformat()}, symbol=symbol)
        ctx.ensure("filings", "fetch-filings",
                   {"symbol": symbol, "start": sejak_filing.isoformat(),
                    "end": ctx.as_of.isoformat()}, symbol=symbol)
        ctx.ensure("corporate_actions", "fetch-corporate-actions",
                   {"symbol": symbol, "start": sejak_aksi.isoformat(),
                    "end": ctx.as_of.isoformat()}, symbol=symbol,
                   where="symbol = ?", where_params=[symbol])

        # Kosong untuk ticker ini vs kosong untuk semua ticker adalah dua hal
        # yang sangat berbeda, dan cuma satu di antaranya temuan.
        if all(ctx.frame(t).empty for t in ("suspensions", "filings", "corporate_actions")):
            return Finding.unavailable(
                "tabel suspensi, filings, dan aksi korporasi kosong di warehouse — "
                "belum diisi, bukan berarti emiten bersih"
            )

        susp = ctx.symbol_frame("suspensions", symbol, since=sejak_suspensi)
        filings = ctx.symbol_frame("filings", symbol, since=sejak_filing)
        aksi = ctx.symbol_frame("corporate_actions", symbol, since=sejak_aksi)

        poin = 0.0
        bukti = []

        # ── suspensi ────────────────────────────────────────────────────────
        if not susp.empty:
            terakhir = susp.iloc[-1]
            mulai = pd.to_datetime(terakhir["start_date"]).date()
            alasan = str(terakhir.get("reason") or "").lower()
            tidak_wajar = any(k in alasan for k in ALASAN_TIDAK_WAJAR)
            poin += POIN_SUSPENSI + (POIN_SUSPENSI_TIDAK_WAJAR if tidak_wajar else 0)
            params = {"symbol": symbol, "start": sejak_suspensi.isoformat(),
                      "end": ctx.as_of.isoformat()}
            bukti.append(self.evidence(
                "sss.prior_suspension", "Suspensi terakhir", str(mulai),
                mulai.strftime("%d-%m-%Y"), endpoint="fetch-suspensions",
                params=params, as_of=mulai))
            bukti.append(self.evidence(
                "sss.suspension_count", f"Jumlah suspensi {SUSPENSI_BULAN} bulan terakhir",
                int(len(susp)), f"{len(susp)} kali", endpoint="fetch-suspensions",
                params=params, as_of=mulai))
            if tidak_wajar:
                bukti.append(self.evidence(
                    "sss.suspension_unusual", "Alasan suspensi terkait pergerakan tidak wajar",
                    True, "ya", endpoint="fetch-suspensions", params=params, as_of=mulai))

        # ── filing insider ──────────────────────────────────────────────────
        # vocab-ok: pola pencocok jenis transaksi di data Sectors, bukan teks keluaran
        pola_jual = "sell|jual"
        jual = filings[
            filings["transaction_type"].astype(str).str.lower().str.contains(pola_jual, na=False)
        ] if not filings.empty else filings
        if not jual.empty:
            poin += min(CAP_INSIDER, POIN_INSIDER_JUAL * len(jual))
            tanggal = pd.to_datetime(jual["filing_date"]).max().date()
            bukti.append(self.evidence(
                "sss.insider_sells", f"Transaksi jual insider {FILING_HARI} hari terakhir",
                int(len(jual)), f"{len(jual)} transaksi", endpoint="fetch-filings",
                params={"symbol": symbol, "transaction_type": "sell",
                        "start": sejak_filing.isoformat()},
                as_of=tanggal))

        # ── aksi korporasi ──────────────────────────────────────────────────
        if not aksi.empty:
            tipe = aksi["action_type"].astype(str).str.lower()
            berisiko = aksi[tipe.apply(lambda t: any(k in t for k in AKSI_BERISIKO))]
            if not berisiko.empty:
                poin += min(CAP_AKSI, POIN_RIGHTS_ISSUE * len(berisiko))
                tanggal = pd.to_datetime(berisiko["action_date"]).max().date()
                bukti.append(self.evidence(
                    "sss.rights_issues",
                    f"Rights issue / private placement {AKSI_BULAN} bulan terakhir",
                    int(len(berisiko)), f"{len(berisiko)} kali",
                    endpoint="fetch-corporate-actions",
                    params={"symbol": symbol, "start": sejak_aksi.isoformat(),
                            "end": ctx.as_of.isoformat()},
                    as_of=tanggal))

        if not bukti:
            # Diperiksa, bersih. Itu temuan, dan harus terlihat di buku bukti —
            # kalau tidak, komponen ini akan tampak "tidak diselidiki" di UI.
            bukti.append(self.evidence(
                "sss.clean", "Peristiwa struktural terdeteksi", 0, "tidak ada",
                endpoint="fetch-suspensions",
                params={"symbol": symbol, "start": sejak_suspensi.isoformat(),
                        "end": ctx.as_of.isoformat()},
                as_of=ctx.as_of))

        return Finding(sub_score=min(100.0, poin), evidence=bukti)
