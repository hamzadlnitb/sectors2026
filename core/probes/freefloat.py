"""FFS — Free Float Scarcity.

Pertanyaan: **berapa kecil saham yang benar-benar beredar?**

Probe paling murah dan paling sering menentukan. Free float 4% berarti seluruh
volume yang terlihat berputar di kolam yang sangat kecil — harga bisa digerakkan
dengan modal yang jauh lebih sedikit daripada yang disangka orang yang cuma
melihat kapitalisasi pasar.

Skor tunggal dan monoton: makin kecil float, makin tinggi skor. Tidak ada
pembobotan tambahan di sini — kombinasinya dengan volume dan konsentrasi broker
sudah diurus pembobotan komposit di lajur Hamzah.
"""

from __future__ import annotations

import pandas as pd

from core.probes.base import BaseProbe, Context, Finding, persen, ramp

# Jangkar terbalik: 50% ke atas → 0, 5% ke bawah → 100.
FLOAT_LONGGAR, FLOAT_KETAT = 0.50, 0.05

BASI_HARI = 400
"""Free float berubah lambat, tapi data 2 tahun lalu bukan lagi keterangan
tentang hari ini. Lewat ambang ini, probe menyerah alih-alih menebak."""


class FreeFloatProbe(BaseProbe):
    name = "free_float"
    component = "FFS"
    endpoints = ("fetch-free-float",)

    def _compute(self, symbol: str, ctx: Context) -> Finding:
        ctx.ensure(
            "free_float", "fetch-free-float", {"symbol": symbol},
            symbol=symbol, where="symbol = ?", where_params=[symbol],
        )

        df = ctx.symbol_frame("free_float", symbol, date_column="as_of")
        df = df[df["free_float_pct"].notna()]
        if df.empty:
            return Finding.unavailable(f"free float {symbol} tidak tersedia di warehouse")

        baris = df.iloc[-1]
        pct = float(baris["free_float_pct"])
        if not 0 < pct <= 1:
            return Finding.unavailable(
                f"free float {pct} di luar rentang wajar 0–1 — data tidak dipakai"
            )

        berlaku = baris["as_of"]
        berlaku = pd.to_datetime(berlaku).date() if pd.notna(berlaku) else None
        if berlaku is None:
            return Finding.unavailable(
                "free float tidak membawa tanggal berlaku — tidak bisa dipakai point-in-time"
            )
        umur = (ctx.as_of - berlaku).days
        if umur > BASI_HARI:
            return Finding.unavailable(
                f"data free float berumur {umur} hari (per {berlaku}) — terlalu basi"
            )

        return Finding(
            sub_score=ramp(-pct, -FLOAT_LONGGAR, -FLOAT_KETAT),
            evidence=[
                self.evidence("ffs.pct", "Free float", round(pct, 4), persen(pct),
                              endpoint="fetch-free-float", params={"symbol": symbol},
                              as_of=berlaku),
                self.evidence("ffs.data_age_days", "Umur data free float", umur,
                              f"{umur} hari", endpoint="fetch-free-float",
                              params={"symbol": symbol}, as_of=berlaku),
            ],
        )
