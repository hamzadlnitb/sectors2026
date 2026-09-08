"""VAS — Volume Anomaly Score.

Pertanyaan: **volume hari ini berapa sigma di atas baseline 90 hari?**

Memakai z-score robust (median + MAD), bukan mean + standar deviasi. Alasannya
bukan selera statistik: satu lonjakan sebelumnya di dalam jendela baseline akan
menggelembungkan standar deviasi dan menyembunyikan lonjakan hari ini — persis
mode kegagalan yang paling ingin kita tangkap, karena saham yang digoreng jarang
meledak sekali saja. Median dan MAD tidak terpengaruh pencilan.

Skala: 1,4826 × MAD menyamakan MAD dengan standar deviasi pada sebaran normal,
jadi "σ" di layar tetap berarti seperti yang orang harapkan.
"""

from __future__ import annotations

import pandas as pd

from core.probes.base import BaseProbe, Context, Finding, last_session, ramp, sigma

BASELINE_SESSIONS = 90
MIN_BASELINE = 30
"""Di bawah ini z-score jadi tebakan. IPO baru masuk ke sini, bukan ke skor nol."""

MAD_TO_SIGMA = 1.4826

# Jangkar skor: 0σ → 0, 6σ → 100.
Z_LOW, Z_HIGH = 0.0, 6.0


class VolumeAnomalyProbe(BaseProbe):
    name = "volume_anomaly"
    component = "VAS"
    endpoints = ("fetch-daily-transaction",)

    def _compute(self, symbol: str, ctx: Context) -> Finding:
        window = ctx.sessions(BASELINE_SESSIONS + 30)
        since = window[0] if window else None
        ctx.ensure(
            "daily_transaction", "fetch-daily-transaction",
            {"symbol": symbol, "start": since.isoformat() if since else None,
             "end": ctx.as_of.isoformat()},
            symbol=symbol, where="symbol = ?", where_params=[symbol],
        )

        df = ctx.symbol_frame("daily_transaction", symbol, since=since)
        df = df[df["volume"].notna()]
        if df.empty:
            return Finding.unavailable(
                f"tidak ada data transaksi harian untuk {symbol} di warehouse"
            )

        volumes = df["volume"].astype(float).to_numpy()
        latest_volume = float(volumes[-1])
        baseline = volumes[-(BASELINE_SESSIONS + 1):-1]
        if len(baseline) < MIN_BASELINE:
            return Finding.unavailable(
                f"riwayat volume hanya {len(baseline)} hari bursa, minimum {MIN_BASELINE} "
                f"— terlalu pendek untuk baseline yang berarti"
            )

        median = float(pd.Series(baseline).median())
        mad = float(pd.Series(abs(baseline - median)).median()) * MAD_TO_SIGMA
        if mad <= 0:
            return Finding.unavailable(
                "sebaran volume baseline nol (perdagangan terlalu tipis) — z-score tidak terdefinisi"
            )

        z = (latest_volume - median) / mad
        rasio = latest_volume / median if median else float("nan")
        day = last_session(df) or ctx.as_of
        params = {"symbol": symbol, "start": str(df["trade_date"].min())[:10],
                  "end": str(day)}

        return Finding(
            sub_score=ramp(z, Z_LOW, Z_HIGH),
            evidence=[
                self.evidence("vas.zscore", "Z-score volume vs baseline 90 hari",
                              round(z, 2), sigma(z), endpoint="fetch-daily-transaction",
                              params=params, as_of=day),
                self.evidence("vas.volume_ratio", "Volume hari terakhir vs median baseline",
                              round(rasio, 2), f"{rasio:.1f}×".replace(".", ","),
                              endpoint="fetch-daily-transaction", params=params, as_of=day),
            ],
        )
