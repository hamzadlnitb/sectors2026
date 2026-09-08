"""BCI — Broker Concentration Index.

Pertanyaan: **berapa persen net buy dikuasai 3 broker teratas, dan seberapa
terpusat sebarannya?**

Dua angka, bukan satu, karena keduanya bisa berbeda arah: pangsa 3 teratas 70%
yang terbagi rata 24/23/23 berbeda watak dari 60/6/4. HHI menangkap perbedaan
itu, pangsa teratas tidak.

Yang dijumlahkan hanya **net buy positif**. Yang kita cari adalah pihak yang
mengumpulkan barang — sisi jualnya sudah ditangkap FRD dan SSS, dan mencampur
keduanya membuat HHI kehilangan arti.
"""

from __future__ import annotations

from core.probes.base import BaseProbe, Context, Finding, last_session, ramp

WINDOW_SESSIONS = 20
MIN_BROKERS = 3
"""Di bawah 3 broker, 'pangsa 3 teratas' tidak berarti apa-apa."""

# Jangkar skor. Pangsa 3 teratas di IDX lazimnya 35–50% pada saham likuid;
# 85% berarti praktis hanya tiga pihak yang mengumpulkan.
SHARE_LOW, SHARE_HIGH = 0.35, 0.85
HHI_LOW, HHI_HIGH = 0.10, 0.40
BOBOT_SHARE, BOBOT_HHI = 0.6, 0.4


class BrokerConcentrationProbe(BaseProbe):
    name = "broker_concentration"
    component = "BCI"
    endpoints = ("fetch-broker-summary-top", "fetch-broker-summary")

    def _compute(self, symbol: str, ctx: Context) -> Finding:
        window = ctx.sessions(WINDOW_SESSIONS)
        since = window[0] if window else None
        ctx.ensure(
            "broker_summary", "fetch-broker-summary-top",
            {"symbol": symbol, "start": since.isoformat() if since else None,
             "end": ctx.as_of.isoformat()},
            symbol=symbol, where="symbol = ?", where_params=[symbol],
        )

        df = ctx.symbol_frame("broker_summary", symbol, since=since)
        if df.empty:
            return Finding.unavailable(
                f"tidak ada ringkasan broker untuk {symbol} dalam {WINDOW_SESSIONS} hari bursa "
                f"terakhir"
            )

        net = (df.groupby("broker_code")["net_value"].sum()
                 .sort_values(ascending=False))
        pembeli = net[net > 0]
        if len(pembeli) < MIN_BROKERS:
            return Finding.unavailable(
                f"hanya {len(pembeli)} broker dengan net buy positif — di bawah {MIN_BROKERS}, "
                f"konsentrasi tidak bisa diukur"
            )

        total = float(pembeli.sum())
        shares = pembeli / total
        top3 = float(shares.head(3).sum())
        hhi = float((shares ** 2).sum())

        skor = BOBOT_SHARE * ramp(top3, SHARE_LOW, SHARE_HIGH) + \
            BOBOT_HHI * ramp(hhi, HHI_LOW, HHI_HIGH)

        day = last_session(df) or ctx.as_of
        params = {"symbol": symbol, "start": str(df["trade_date"].min())[:10], "end": str(day)}
        tiga = ", ".join(shares.head(3).index.tolist())

        return Finding(
            sub_score=skor,
            evidence=[
                self.evidence("bci.top3_share", "Pangsa net buy 3 broker teratas",
                              round(top3, 4), f"{top3 * 100:.0f}%",
                              endpoint="fetch-broker-summary-top", params=params, as_of=day),
                self.evidence("bci.hhi", "Indeks Herfindahl konsentrasi broker",
                              round(hhi, 4), f"{hhi:.2f}".replace(".", ","),
                              endpoint="fetch-broker-summary", params=params, as_of=day),
                self.evidence("bci.top3_codes", "Kode 3 broker net buy teratas",
                              tiga, tiga, endpoint="fetch-broker-summary-top",
                              params=params, as_of=day),
                self.evidence("bci.broker_count", "Jumlah broker dengan net buy positif",
                              int(len(pembeli)), f"{len(pembeli)} broker",
                              endpoint="fetch-broker-summary", params=params, as_of=day),
            ],
        )
