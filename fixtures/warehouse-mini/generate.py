"""Bangkitkan fixtures/warehouse-mini/ — potongan warehouse untuk tes tanpa jaringan.

⚠️  SELURUH ANGKA DI SINI KARANGAN. Ticker FIXA–FIXF fiktif. Berkas ini TIDAK
    BOLEH dipakai untuk klaim apa pun tentang emiten sungguhan, dan tidak boleh
    tercampur dengan data/warehouse/ yang berisi tarikan Sectors asli.

Gunanya satu: enam probe harus bisa diuji tanpa API key dan tanpa jaringan, tiap
kali CI jalan. Data asli tidak bisa dipakai untuk itu — ia butuh kredit, berubah
tiap hari, dan tidak memuat kasus tepi yang justru paling ingin kita tes.

Enam ticker = enam bentuk masalah yang harus ditangani probe:

    FIXA  tenang        skor rendah di semua komponen
    FIXB  waspada       broker terkonsentrasi, volume 4σ, harga naik laba turun
    FIXC  sangat wasp.  free float 4%, volume 6σ, rights issue, pernah disuspend
    FIXD  IPO baru      riwayat 12 hari — probe wajib bilang "data kurang", bukan crash
    FIXE  tersuspend    perdagangan berhenti sebelum as_of
    FIXF  data bolong   ada di daily_close, tapi tabel lain kosong untuknya

Baris SETELAH as_of sengaja ikut ditulis (2026-09-08 dan 09-09). Itu umpan untuk
tes point-in-time: probe yang bocor lookahead akan terlihat karena angkanya
berubah. [contracts/CHANGES.md C1, catatan penutup]

    python fixtures/warehouse-mini/generate.py
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.ingest.warehouse import Warehouse  # noqa: E402

OUT = Path(__file__).resolve().parent
AS_OF = date(2026, 9, 5)          # sama dengan fixtures/transcripts/
FUTURE = [date(2026, 9, 8), date(2026, 9, 9)]  # umpan lookahead
SESSIONS = 140                     # hari bursa mundur dari as_of
SEED = 20260905

MILIAR = 1_000_000_000


def sessions_until(end: date, count: int) -> list[date]:
    """Hari bursa mundur dari end. Sabtu-Minggu dilewati.

    Libur nasional IDX sengaja tidak dimodelkan — fixture ini tidak berpura-pura
    jadi kalender bursa. Kode produksi memakai tanggal yang benar-benar ada di
    daily_close (lihat warehouse.trading_days), bukan hari kerja hasil hitungan.
    """
    out: list[date] = []
    cursor = end
    while len(out) < count:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(out)


DAYS = sessions_until(AS_OF, SESSIONS)
ALL_DAYS = DAYS + FUTURE


def ramp(n: int, start: float, end: float) -> list[float]:
    if n == 1:
        return [end]
    step = (end - start) / (n - 1)
    return [start + step * i for i in range(n)]


class Builder:
    """Satu ticker, satu cerita. Seed tetap → berkas identik tiap kali dibangkitkan."""

    def __init__(self, seed: int = SEED) -> None:
        self.rnd = random.Random(seed)
        self.close: list[dict] = []
        self.daily: list[dict] = []
        self.broker: list[dict] = []
        self.foreign: list[dict] = []
        self.float_: list[dict] = []
        self.susp: list[dict] = []
        self.filings: list[dict] = []
        self.actions: list[dict] = []
        self.fin: list[dict] = []
        self.profile: list[dict] = []

    # ── harga & volume ──────────────────────────────────────────────────────
    def price_series(self, days: list[date], base: float, drift: float,
                     jitter: float = 0.012) -> list[float]:
        prices, price = [], base
        for _ in days:
            price *= 1 + drift + self.rnd.gauss(0, jitter)
            prices.append(round(max(price, 50.0), 2))
        return prices

    def volume_series(self, days: list[date], mean: float, spikes: dict[int, float]) -> list[int]:
        """Volume dasar lognormal + lonjakan di posisi tertentu dari belakang.

        spikes memetakan "berapa hari bursa dari as_of" -> kelipatan terhadap mean.
        Titik acuannya as_of, BUKAN akhir deret: deret memuat hari sesudah as_of
        sebagai umpan lookahead, dan lonjakan yang mendarat di sana tidak akan
        pernah terlihat probe.
        Sebaran lognormal(0, 0.28) memberi MAD sekitar 0,28x mean, jadi
        kelipatan 2,15x jatuh di sekitar 4 sigma dan 2,80x di sekitar 6 sigma.
        Itu yang bikin cerita tiap ticker terbaca di skor, bukan angka bebas.
        """
        vols = [max(1000, int(self.rnd.lognormvariate(0, 0.28) * mean)) for _ in days]
        visible = [i for i, d in enumerate(days) if d <= AS_OF]
        if not visible:
            return vols
        anchor = visible[-1]
        for back, factor in spikes.items():
            idx = anchor - (back - 1)
            if 0 <= idx < len(days):
                vols[idx] = int(mean * factor)
        return vols

    def add_market(self, symbol: str, days: list[date], prices: list[float],
                   volumes: list[int], market_cap: int) -> None:
        for d, p, v in zip(days, prices, volumes, strict=True):
            self.close.append({"trade_date": d, "symbol": symbol, "close_price": p})
            self.daily.append({
                "trade_date": d, "symbol": symbol, "close_price": p,
                "volume": v, "market_cap": market_cap,
            })

    # ── broker ──────────────────────────────────────────────────────────────
    def add_broker(self, symbol: str, days: list[date], codes: list[str],
                   weights: list[float], scale: float) -> None:
        """Net buy per broker. weights menentukan seberapa terkonsentrasi."""
        for d in days:
            for code, w in zip(codes, weights, strict=True):
                net = scale * w * self.rnd.uniform(0.6, 1.4)
                buy = abs(net) * self.rnd.uniform(1.2, 2.0)
                self.broker.append({
                    "trade_date": d, "symbol": symbol, "broker_code": code,
                    "net_value": round(net, 2), "buy_value": round(buy, 2),
                    "sell_value": round(buy - net, 2),
                })

    def add_foreign(self, symbol: str, days: list[date], share_of_turnover: float,
                    noise: float = 0.4) -> None:
        """Arus asing sebagai PORSI nilai transaksi harian, bukan nominal bebas.

        Negatif = asing keluar. Dinyatakan relatif karena itu juga yang diukur
        probe FRD: keluar Rp 50 M dari saham lapis tiga tidak sebanding dengan
        Rp 50 M dari bank besar. Nominal bebas bikin fixture gampang tidak
        konsisten dengan volumenya sendiri.
        """
        turnover = {
            r["trade_date"]: (r["close_price"] or 0) * (r["volume"] or 0)
            for r in self.daily if r["symbol"] == symbol
        }
        for d in days:
            nilai = turnover.get(d, 0.0)
            self.foreign.append({
                "trade_date": d, "symbol": symbol,
                "net_value": round(
                    share_of_turnover * nilai * self.rnd.uniform(1 - noise, 1 + noise), 2
                ),
            })

    # ── fundamental ─────────────────────────────────────────────────────────
    def add_financials(self, symbol: str, quarters: int, revenue0: float,
                       income0: float, income_growth: float) -> None:
        """Kuartal mundur dari Q2-2026, laporan terbit ±45 hari setelah tutup buku."""
        end = date(2026, 6, 30)
        for i in range(quarters):
            months = 3 * i
            year = end.year - (months // 12)
            month = end.month - (months % 12)
            if month <= 0:
                month += 12
                year -= 1
            period = date(year, month, min(30, 28 if month == 2 else 30))
            factor = (1 + income_growth) ** (-i)
            self.fin.append({
                "symbol": symbol, "report_date": period + timedelta(days=45),
                "revenue": int(revenue0 * (1.02 ** -i)),
                "net_income": int(income0 * factor),
                "total_assets": int(revenue0 * 4.2),
            })

    def add_profile(self, symbol: str, name: str, sub_sector: str,
                    market_cap: int, listing: date) -> None:
        self.profile.append({
            "symbol": symbol, "company_name": name, "sub_sector": sub_sector,
            "market_cap": market_cap, "listing_date": listing,
        })


def build() -> Builder:
    b = Builder()

    # ── FIXA — tenang. Semua komponen harus keluar rendah. ──────────────────
    b.add_profile("FIXA", "Fiksi Antariksa Tbk", "banks", 1_100_000 * MILIAR,
                  date(2011, 3, 14))
    prices = b.price_series(ALL_DAYS, 9200, 0.0004)
    b.add_market("FIXA", ALL_DAYS, prices,
                 b.volume_series(ALL_DAYS, 5_000_000, {1: 1.10}),
                 1_100_000 * MILIAR)
    b.add_broker("FIXA", ALL_DAYS[-40:],
                 ["YP", "PD", "CC", "NI", "AK", "KZ", "BK", "MG", "DR", "XA", "YU", "ZP"],
                 [0.12, 0.11, 0.10, 0.10, 0.09, 0.09, 0.08, 0.08, 0.08, 0.05, 0.05, 0.05],
                 40 * MILIAR)
    b.add_foreign("FIXA", ALL_DAYS[-60:], 0.012)    # asing masuk tipis
    b.float_.append({"symbol": "FIXA", "free_float_pct": 0.62, "as_of": date(2026, 6, 30)})
    b.add_financials("FIXA", 8, 42_000 * MILIAR, 9_500 * MILIAR, 0.11)

    # ── FIXB — waspada. Harga naik tajam, laba turun, broker terkonsentrasi. ─
    b.add_profile("FIXB", "Fiksi Bahari Nusantara Tbk", "basic-materials",
                  8_400 * MILIAR, date(2019, 8, 2))
    tail = 90
    base = b.price_series(ALL_DAYS[:-tail], 620, 0.0002)
    naik = ramp(tail, base[-1], base[-1] * 2.42)  # +142% dalam 90 hari bursa
    b.add_market("FIXB", ALL_DAYS, base + [round(p, 2) for p in naik],
                 b.volume_series(ALL_DAYS, 12_000_000, {3: 1.55, 2: 1.80, 1: 2.15}),
                 8_400 * MILIAR)
    b.add_broker("FIXB", ALL_DAYS[-40:],
                 ["XL", "RF", "IF", "YP", "PD", "CC", "NI", "AK"],
                 [0.34, 0.27, 0.17, 0.06, 0.05, 0.05, 0.03, 0.03], 55 * MILIAR)
    b.add_foreign("FIXB", ALL_DAYS[-60:], -0.085)   # keluar 8,5% nilai transaksi
    b.float_.append({"symbol": "FIXB", "free_float_pct": 0.28, "as_of": date(2026, 6, 30)})
    b.add_financials("FIXB", 8, 3_100 * MILIAR, 210 * MILIAR, -0.08)
    for i, d in enumerate([date(2026, 7, 14), date(2026, 8, 3), date(2026, 8, 27)]):
        b.filings.append({
            "filing_date": d, "symbol": "FIXB", "holder_name": f"Pemegang Saham {i + 1}",
            "holder_type": "insider", "transaction_type": "sell",
            "shares": 14_000_000 + i * 3_000_000, "price": 900.0 + i * 220,
        })
    b.actions.append({"symbol": "FIXB", "action_date": date(2025, 12, 8),
                      "action_type": "stock_split", "detail": "Rasio 1:5"})

    # ── FIXC — sangat waspada. Float 4%, volume 6σ, riwayat suspensi. ───────
    b.add_profile("FIXC", "Fiksi Cakrawala Properti Tbk", "properties-real-estate",
                  1_250 * MILIAR, date(2021, 11, 30))
    ekor = 20
    awal = b.price_series(ALL_DAYS[:-ekor], 148, 0.0001)
    lonjak = ramp(ekor, awal[-1], awal[-1] * 1.8)
    b.add_market("FIXC", ALL_DAYS, awal + [round(p, 2) for p in lonjak],
                 b.volume_series(ALL_DAYS, 2_200_000, {3: 1.70, 2: 2.20, 1: 3.00}),
                 1_250 * MILIAR)
    b.add_broker("FIXC", ALL_DAYS[-40:], ["RF", "XL", "YP", "PD", "CC"],
                 [0.47, 0.31, 0.09, 0.08, 0.05], 18 * MILIAR)
    b.add_foreign("FIXC", ALL_DAYS[-60:], -0.165)   # keluar 16,5%, mendekati ekstrem
    b.float_.append({"symbol": "FIXC", "free_float_pct": 0.04, "as_of": date(2026, 6, 30)})
    b.add_financials("FIXC", 8, 480 * MILIAR, -35 * MILIAR, 0.05)
    b.susp.append({
        "symbol": "FIXC", "start_date": date(2025, 11, 14), "end_date": date(2025, 11, 18),
        "reason": "Penghentian sementara terkait pergerakan harga di luar kebiasaan",
    })
    for d, detail in [
        (date(2025, 4, 22), "Rights issue 1:2, harga pelaksanaan Rp 100"),
        (date(2026, 5, 18), "Rights issue 2:3, harga pelaksanaan Rp 120"),
    ]:
        b.actions.append({"symbol": "FIXC", "action_date": d,
                          "action_type": "rights_issue", "detail": detail})
    b.filings.append({
        "filing_date": date(2026, 8, 19), "symbol": "FIXC", "holder_name": "Direktur Utama",
        "holder_type": "insider", "transaction_type": "sell",
        "shares": 51_000_000, "price": 218.0,
    })

    # ── FIXD — IPO baru. Riwayat 12 hari; probe wajib menyerah dengan alasan. ─
    b.add_profile("FIXD", "Fiksi Digital Ventura Tbk", "technology", 640 * MILIAR,
                  date(2026, 8, 20))
    muda = [d for d in ALL_DAYS if d >= date(2026, 8, 20)]
    b.add_market("FIXD", muda, b.price_series(muda, 328, 0.004),
                 b.volume_series(muda, 3_400_000, {1: 1.9}), 640 * MILIAR)
    b.float_.append({"symbol": "FIXD", "free_float_pct": 0.35, "as_of": date(2026, 8, 20)})
    b.add_financials("FIXD", 1, 96 * MILIAR, 4 * MILIAR, 0.0)

    # ── FIXE — tersuspend sebelum as_of. Data berhenti di tengah jalan. ─────
    b.add_profile("FIXE", "Fiksi Energi Khatulistiwa Tbk", "energy", 2_900 * MILIAR,
                  date(2016, 6, 9))
    sampai = [d for d in ALL_DAYS if d <= date(2026, 8, 31)]
    b.add_market("FIXE", sampai, b.price_series(sampai, 1_180, -0.001),
                 b.volume_series(sampai, 1_800_000, {}), 2_900 * MILIAR)
    b.add_broker("FIXE", sampai[-30:], ["YP", "PD", "CC", "NI"],
                 [0.31, 0.28, 0.22, 0.19], 9 * MILIAR)
    b.float_.append({"symbol": "FIXE", "free_float_pct": 0.15, "as_of": date(2026, 6, 30)})
    b.susp.append({
        "symbol": "FIXE", "start_date": date(2026, 9, 1), "end_date": None,
        "reason": "Penghentian sementara menunggu keterbukaan informasi",
    })
    b.add_financials("FIXE", 8, 1_400 * MILIAR, -80 * MILIAR, 0.02)

    # ── FIXF — bolong. Ada harga, tidak ada apa-apa lagi. ───────────────────
    b.add_profile("FIXF", "Fiksi Fajar Sentosa Tbk", "consumer-cyclicals",
                  310 * MILIAR, date(2013, 2, 18))
    for d, p in zip(ALL_DAYS, b.price_series(ALL_DAYS, 74, 0.0), strict=True):
        b.close.append({"trade_date": d, "symbol": "FIXF", "close_price": p})

    return b


TABEL = {
    "daily_close": "close", "daily_transaction": "daily", "broker_summary": "broker",
    "foreign_flow": "foreign", "free_float": "float_", "suspensions": "susp",
    "filings": "filings", "corporate_actions": "actions",
    "quarterly_financials": "fin", "company_profile": "profile",
}


def main() -> int:
    for stale in OUT.glob("*.parquet"):
        stale.unlink()  # bangun ulang dari nol, jangan menumpuk baris lama

    b = build()
    wh = Warehouse(OUT)
    print(f"fixtures/warehouse-mini/  as_of={AS_OF}  seed={SEED}  (SELURUH ANGKA KARANGAN)")
    for table, attr in TABEL.items():
        rows = getattr(b, attr)
        total = wh.write(table, pd.DataFrame(rows))
        print(f"  {table:<22} {total:>7} baris")
    # as_of kanonik ditulis ke berkas, bukan cuma ke docstring: deret ini memuat
    # baris SETELAH as_of sebagai umpan lookahead, jadi max(trade_date) BUKAN
    # tanggal acuan yang benar. make demo membacanya dari sini.
    (OUT / "meta.json").write_text(json.dumps({
        "as_of": AS_OF.isoformat(),
        "seed": SEED,
        "sessions": SESSIONS,
        "lookahead_bait": [d.isoformat() for d in FUTURE],
        "synthetic": True,
        "note": "SELURUH ANGKA KARANGAN. Ticker FIXA-FIXF fiktif.",
    }, indent=2) + "\n", encoding="utf-8")

    print()
    print(wh.describe(as_of=AS_OF))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
