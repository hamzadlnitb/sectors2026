"""PFD — Price–Fundamental Divergence.

Pertanyaan: **harga naik 200% sementara labanya flat atau rugi?**

Divergensi = return 90 hari bursa − pertumbuhan laba bersih year-on-year.
Keduanya pecahan, jadi selisihnya terbaca langsung: harga +142% dengan laba −8%
memberi divergensi 1,50.

Laba dibandingkan **year-on-year**, bukan kuartal sebelumnya, karena banyak
emiten IDX musiman dan perbandingan kuartal berurutan akan menandai pola musiman
sebagai anomali.

Kalau laporan keuangan tidak ada, probe menyerah dengan alasan — TIDAK memakai
return saja. Return tinggi tanpa pembanding fundamental bukan divergensi; itu
cuma harga naik, dan menyebutnya divergensi berarti mengarang temuan.
"""

from __future__ import annotations

import pandas as pd

from core.probes.base import BaseProbe, Context, Finding, last_session, persen, ramp

RETURN_SESSIONS = 90
MIN_SESSIONS = 30
YOY_LAG_QUARTERS = 4

# Jangkar: divergensi 0,25 mulai berarti; 2,50 (mis. +240% dengan laba flat)
# sudah ekstrem.
DIV_LOW, DIV_HIGH = 0.25, 2.50


class PriceFundamentalProbe(BaseProbe):
    name = "price_fundamental"
    component = "PFD"
    endpoints = ("fetch-close", "fetch-quarterly-financials")

    def _compute(self, symbol: str, ctx: Context) -> Finding:
        window = ctx.sessions(RETURN_SESSIONS + 10)
        since = window[0] if window else None

        harga = ctx.symbol_frame("daily_close", symbol, since=since)
        if len(harga) < MIN_SESSIONS:
            return Finding.unavailable(
                f"riwayat harga hanya {len(harga)} hari bursa, minimum {MIN_SESSIONS} "
                f"— return 90 hari tidak bisa dihitung"
            )

        harga = harga[harga["close_price"].notna()]
        awal = float(harga["close_price"].iloc[0])
        akhir = float(harga["close_price"].iloc[-1])
        if awal <= 0:
            return Finding.unavailable("harga awal jendela nol atau negatif — return tidak sah")
        return_90d = akhir / awal - 1

        ctx.ensure(
            "quarterly_financials", "fetch-quarterly-financials",
            {"symbol": symbol, "n_quarters": 8},
            symbol=symbol, where="symbol = ?", where_params=[symbol],
        )
        fin = ctx.symbol_frame("quarterly_financials", symbol, date_column="report_date")
        fin = fin[fin["net_income"].notna()]
        if len(fin) <= YOY_LAG_QUARTERS:
            return Finding.unavailable(
                f"laporan keuangan tersedia {len(fin)} kuartal (per {ctx.as_of}), butuh "
                f"lebih dari {YOY_LAG_QUARTERS} untuk perbandingan year-on-year"
            )

        terbaru = float(fin["net_income"].iloc[-1])
        setahun_lalu = float(fin["net_income"].iloc[-1 - YOY_LAG_QUARTERS])
        if setahun_lalu == 0:
            return Finding.unavailable(
                "laba bersih setahun lalu nol — pertumbuhan year-on-year tidak terdefinisi"
            )

        # abs() di penyebut menjaga arah tetap benar saat pembandingnya rugi:
        # rugi 100 M jadi rugi 50 M adalah PERBAIKAN, dan tanpa abs() tandanya terbalik.
        laba_yoy = (terbaru - setahun_lalu) / abs(setahun_lalu)
        divergensi = return_90d - laba_yoy

        day = last_session(harga) or ctx.as_of
        params_harga = {"symbol": symbol, "start": str(harga["trade_date"].min())[:10],
                        "end": str(day)}
        params_fin = {"symbol": symbol, "n_quarters": 8}
        periode = pd.to_datetime(fin["report_date"].iloc[-1]).date()

        return Finding(
            sub_score=ramp(divergensi, DIV_LOW, DIV_HIGH),
            evidence=[
                self.evidence("pfd.return_90d", "Return 90 hari bursa", round(return_90d, 4),
                              f"{'+' if return_90d >= 0 else ''}{persen(return_90d)}",
                              endpoint="fetch-close", params=params_harga, as_of=day),
                self.evidence("pfd.earnings_change", "Perubahan laba bersih year-on-year",
                              round(laba_yoy, 4),
                              f"{'+' if laba_yoy >= 0 else ''}{persen(laba_yoy)}",
                              endpoint="fetch-quarterly-financials", params=params_fin,
                              as_of=periode),
                self.evidence("pfd.divergence", "Selisih return terhadap pertumbuhan laba",
                              round(divergensi, 4),
                              f"{'+' if divergensi >= 0 else ''}{persen(divergensi)} poin",
                              endpoint="fetch-quarterly-financials", params=params_fin,
                              as_of=periode),
            ],
        )
