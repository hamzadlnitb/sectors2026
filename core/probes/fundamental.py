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

N_KUARTAL = YOY_LAG_QUARTERS + 1
"""Kuartal yang diminta: minimum untuk year-on-year. fetch-quarterly-financials
menagih 1 kredit PER KUARTAL yang dikembalikan — minta 8 berarti bayar 8 untuk
tiga kuartal yang tidak pernah dibaca. Selaras `units=5` di routing."""

# Jangkar: divergensi 0,25 mulai berarti; 2,50 (mis. +240% dengan laba flat)
# sudah ekstrem.
DIV_LOW, DIV_HIGH = 0.25, 2.50


class PriceFundamentalProbe(BaseProbe):
    name = "price_fundamental"
    component = "PFD"
    # Yang dianggarkan = yang benar-benar dibeli. Dulu fetch-close ikut
    # dianggarkan padahal tidak pernah dipanggil, sementara harga dibaca dari
    # warehouse tanpa disegarkan — return 90 hari bisa berhenti di tanggal
    # backfill. Sekarang harga disegarkan lewat fetch-daily-transaction,
    # sama seperti VAS. [AUDIT B4]
    endpoints = ("fetch-daily-transaction", "fetch-quarterly-financials")

    def _compute(self, symbol: str, ctx: Context) -> Finding:
        window = ctx.sessions(RETURN_SESSIONS + 10)
        since = window[0] if window else None

        ctx.ensure(
            "daily_transaction", "fetch-daily-transaction",
            {"symbol": symbol, "start": since.isoformat() if since else None,
             "end": ctx.as_of.isoformat()},
            symbol=symbol, where="symbol = ?", where_params=[symbol], fresh=True,
        )
        harga = ctx.price_history(symbol, since=since)
        if len(harga) < MIN_SESSIONS:
            return Finding.unavailable(
                f"riwayat harga hanya {len(harga)} hari bursa, minimum {MIN_SESSIONS} "
                f"— return 90 hari tidak bisa dihitung"
            )

        awal = float(harga["close_price"].iloc[0])
        akhir = float(harga["close_price"].iloc[-1])
        if awal <= 0:
            return Finding.unavailable("harga awal jendela nol atau negatif — return tidak sah")
        return_90d = akhir / awal - 1

        ctx.ensure(
            "quarterly_financials", "fetch-quarterly-financials",
            {"symbol": symbol, "n_quarters": N_KUARTAL},
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
        params_fin = {"symbol": symbol, "n_quarters": N_KUARTAL}
        periode = pd.to_datetime(fin["report_date"].iloc[-1]).date()

        return Finding(
            sub_score=ramp(divergensi, DIV_LOW, DIV_HIGH),
            evidence=[
                self.evidence("pfd.return_90d", "Return 90 hari bursa", round(return_90d, 4),
                              f"{'+' if return_90d >= 0 else ''}{persen(return_90d)}",
                              endpoint="fetch-daily-transaction", params=params_harga,
                              as_of=day),
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
