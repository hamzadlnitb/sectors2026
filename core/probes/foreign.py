"""FRD — Foreign–Retail Divergence.

Pertanyaan: **asing keluar sementara harga naik — apakah barangnya sedang
dilempar ke ritel?**

Butuh DUA syarat sekaligus, dan itu inti probenya:

* arus asing bersih negatif dan besar **relatif terhadap nilai transaksi saham
  itu sendiri** (bukan nominal mentah — keluar Rp 50 M dari saham lapis tiga
  jauh lebih berarti daripada dari bank besar);
* harga justru naik pada periode yang sama.

Kalau harga turun saat asing keluar, itu penjualan biasa, bukan distribusi ke
ritel — dan skornya memang harus rendah. Skor = ramp(rasio) × gerbang(harga),
jadi salah satu syarat tidak terpenuhi berarti skor mendekati nol, bukan
setengah.
"""

from __future__ import annotations

from core.probes.base import BaseProbe, Context, Finding, last_session, persen, ramp, rupiah

WINDOW_SESSIONS = 30
MIN_SESSIONS = 10

# Jangkar: arus keluar 2% dari nilai transaksi periode mulai berarti; 20% ekstrem.
RASIO_LOW, RASIO_HIGH = 0.02, 0.20
# Gerbang harga: kenaikan 15% dalam 30 hari bursa membuka gerbang penuh.
KENAIKAN_PENUH = 0.15


class ForeignFlowProbe(BaseProbe):
    name = "foreign_flow"
    component = "FRD"
    endpoints = ("fetch-foreign-flow", "fetch-daily-transaction")

    def _compute(self, symbol: str, ctx: Context) -> Finding:
        window = ctx.sessions(WINDOW_SESSIONS)
        since = window[0] if window else None
        ctx.ensure(
            "foreign_flow", "fetch-foreign-flow",
            {"symbol": symbol, "start": since.isoformat() if since else None,
             "end": ctx.as_of.isoformat()},
            symbol=symbol, where="symbol = ?", where_params=[symbol],
        )

        asing = ctx.symbol_frame("foreign_flow", symbol, since=since)
        asing = asing[asing["net_value"].notna()]
        if asing.empty:
            return Finding.unavailable(f"tidak ada data arus asing untuk {symbol} di warehouse")
        if len(asing) < MIN_SESSIONS:
            return Finding.unavailable(
                f"arus asing {symbol} baru {len(asing)} hari bursa, minimum {MIN_SESSIONS}"
            )

        pasar = ctx.symbol_frame("daily_transaction", symbol, since=since)
        pasar = pasar[pasar["close_price"].notna()]
        if len(pasar) < MIN_SESSIONS:
            return Finding.unavailable(
                f"data transaksi {symbol} tidak cukup ({len(pasar)} hari) untuk menormalkan "
                f"arus asing"
            )

        net_asing = float(asing["net_value"].sum())
        nilai_transaksi = float(
            (pasar["close_price"].astype(float) * pasar["volume"].fillna(0).astype(float)).sum()
        )
        if nilai_transaksi <= 0:
            return Finding.unavailable(
                "nilai transaksi periode nol — arus asing tidak bisa dinormalkan"
            )

        awal = float(pasar["close_price"].iloc[0])
        akhir = float(pasar["close_price"].iloc[-1])
        perubahan_harga = akhir / awal - 1 if awal > 0 else 0.0

        rasio_keluar = max(0.0, -net_asing) / nilai_transaksi
        gerbang = max(0.0, min(1.0, perubahan_harga / KENAIKAN_PENUH))
        skor = ramp(rasio_keluar, RASIO_LOW, RASIO_HIGH) * gerbang

        day = last_session(pasar) or ctx.as_of
        params = {"symbol": symbol, "start": str(pasar["trade_date"].min())[:10], "end": str(day)}

        return Finding(
            sub_score=skor,
            evidence=[
                self.evidence("frd.foreign_net_30d", "Arus asing bersih 30 hari bursa",
                              round(net_asing, 2), rupiah(net_asing),
                              endpoint="fetch-foreign-flow", params=params, as_of=day),
                self.evidence("frd.outflow_ratio",
                              "Arus keluar asing terhadap nilai transaksi periode",
                              round(rasio_keluar, 4), persen(rasio_keluar, 1),
                              endpoint="fetch-foreign-flow", params=params, as_of=day),
                self.evidence("frd.price_change_30d", "Perubahan harga 30 hari bursa",
                              round(perubahan_harga, 4),
                              f"{'+' if perubahan_harga >= 0 else ''}{persen(perubahan_harga)}",
                              endpoint="fetch-daily-transaction", params=params, as_of=day),
            ],
        )
