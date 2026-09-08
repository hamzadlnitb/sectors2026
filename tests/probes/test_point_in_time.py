"""Probe wajib point-in-time. Ini tes yang menjaga Angka 1 tetap jujur.

Kalibrasi bobot Hamzah menghitung enam sub-skor pada T-1, T-3, T-5, T-10 hari
bursa SEBELUM peristiwa suspensi. Satu probe saja yang membaca data setelah
as_of akan membuat bobot terlihat bagus di backtest dan gagal di dunia nyata,
dan tidak ada yang akan tahu sampai juri praktisi pasar menanyakannya.

Karena itu tesnya bukan "apakah kodenya kelihatan benar", tapi: **tambahkan data
masa depan, jalankan ulang, hasilnya harus identik bit per bit.**

    fixtures/warehouse-mini/ sudah memuat baris 2026-09-08 dan 09-09 sebagai
    umpan. Tes ini menambah lagi yang jauh lebih ekstrem.
"""

from __future__ import annotations

import shutil
from datetime import date, timedelta

import pandas as pd
import pytest

from core.ingest.warehouse import TABLES, Warehouse, trading_days
from core.probes.base import Context
from core.probes.registry import PROBES

AS_OF = date(2026, 9, 5)
SEMUA = list(PROBES.values())
NAMA = [p.name for p in SEMUA]


def hasil(wh: Warehouse, symbol: str, as_of: date = AS_OF) -> dict:
    ctx = Context(as_of=as_of, warehouse=wh, client=None, budget_remaining=25)
    return {
        p.name: (r.sub_score, r.unavailable_reason,
                 tuple((e.id, e.value) for e in r.evidence))
        for p in SEMUA
        for r in [p.run(symbol, ctx)]
    }


@pytest.fixture
def warehouse_salinan(mini: Warehouse, tmp_path) -> Warehouse:
    """Salinan warehouse-mini yang boleh dikotori tes."""
    tujuan = tmp_path / "wh"
    shutil.copytree(mini.path, tujuan, ignore=shutil.ignore_patterns("*.md", "*.py"))
    return Warehouse(tujuan)


def suntik_masa_depan(wh: Warehouse) -> None:
    """Tambahkan data setelah as_of yang MENCOLOK: harga 10x, volume 50x,
    suspensi baru, filing insider, rights issue. Kalau ada yang bocor, angkanya
    akan meloncat, bukan bergeser tipis."""
    besok = AS_OF + timedelta(days=3)
    lusa = AS_OF + timedelta(days=4)
    simbol = ["FIXA", "FIXB", "FIXC", "FIXE", "FIXF"]

    wh.write("daily_close", pd.DataFrame([
        {"trade_date": d, "symbol": s, "close_price": 99_999.0}
        for d in (besok, lusa) for s in simbol
    ]))
    wh.write("daily_transaction", pd.DataFrame([
        {"trade_date": d, "symbol": s, "close_price": 99_999.0,
         "volume": 9_000_000_000, "market_cap": 10**18}
        for d in (besok, lusa) for s in simbol
    ]))
    wh.write("broker_summary", pd.DataFrame([
        {"trade_date": d, "symbol": s, "broker_code": "ZZ",
         "net_value": 9.9e14, "buy_value": 9.9e14, "sell_value": 0.0}
        for d in (besok, lusa) for s in simbol
    ]))
    wh.write("foreign_flow", pd.DataFrame([
        {"trade_date": d, "symbol": s, "net_value": -9.9e14}
        for d in (besok, lusa) for s in simbol
    ]))
    wh.write("free_float", pd.DataFrame([
        {"symbol": s, "free_float_pct": 0.001, "as_of": besok} for s in simbol
    ]))
    wh.write("suspensions", pd.DataFrame([
        {"symbol": s, "start_date": besok, "end_date": None,
         "reason": "Pergerakan harga di luar kebiasaan"} for s in simbol
    ]))
    wh.write("filings", pd.DataFrame([
        {"filing_date": besok, "symbol": s, "holder_name": "X", "holder_type": "insider",
         "transaction_type": "sell", "shares": 10**9, "price": 1.0} for s in simbol
    ]))
    wh.write("corporate_actions", pd.DataFrame([
        {"symbol": s, "action_date": besok, "action_type": "rights_issue",
         "detail": "masa depan"} for s in simbol
    ]))
    wh.write("quarterly_financials", pd.DataFrame([
        {"symbol": s, "report_date": besok, "revenue": 1, "net_income": -(10**15),
         "total_assets": 1} for s in simbol
    ]))


@pytest.mark.parametrize("symbol", ["FIXA", "FIXB", "FIXC", "FIXE", "FIXF"])
def test_data_masa_depan_tidak_mengubah_hasil(warehouse_salinan, symbol):
    """Inti kontrak point-in-time. Bandingkan sebelum vs sesudah penyuntikan."""
    sebelum = hasil(warehouse_salinan, symbol)
    suntik_masa_depan(warehouse_salinan)
    sesudah = hasil(warehouse_salinan, symbol)

    for name in sebelum:
        assert sebelum[name] == sesudah[name], (
            f"probe {name} bocor lookahead pada {symbol}: "
            f"{sebelum[name][0]} -> {sesudah[name][0]}"
        )


def test_penyuntikan_memang_terlihat_kalau_as_of_digeser(warehouse_salinan):
    """Kontrol negatif. Tanpa ini, tes di atas juga hijau kalau penyuntikannya
    ternyata tidak menulis apa-apa — dan kita akan mengira aman padahal buta."""
    sebelum = hasil(warehouse_salinan, "FIXA")
    suntik_masa_depan(warehouse_salinan)
    setelah_geser = hasil(warehouse_salinan, "FIXA", as_of=AS_OF + timedelta(days=5))

    berubah = [n for n in sebelum if sebelum[n][0] != setelah_geser[n][0]]
    assert berubah, "penyuntikan tidak berpengaruh sama sekali — tes utama jadi tidak berarti"


def test_view_warehouse_menyaring_semua_tabel_bertanggal(warehouse_salinan):
    """Penjagaan di lapisan bawah: bukan cuma probe yang tidak melihat masa
    depan — koneksinya memang tidak memuatnya."""
    suntik_masa_depan(warehouse_salinan)
    with warehouse_salinan.connect(as_of=AS_OF) as con:
        for name, spec in TABLES.items():
            if not spec.cut_column or not warehouse_salinan.exists(name):
                continue
            maks = con.execute(f"SELECT max({spec.cut_column}) FROM {name}").fetchone()[0]
            if maks is None:
                continue
            assert maks <= AS_OF, f"{name}.{spec.cut_column} memuat {maks}, setelah as_of"


def test_tanpa_as_of_data_masa_depan_memang_ada(warehouse_salinan):
    """Penyaringan hanya berlaku saat as_of diminta — ingest tetap boleh menulis
    dan membaca seluruh isi warehouse."""
    suntik_masa_depan(warehouse_salinan)
    penuh = warehouse_salinan.frame("daily_close")
    assert pd.to_datetime(penuh["trade_date"]).max().date() > AS_OF


def test_hari_bursa_berhenti_di_as_of(warehouse_salinan):
    suntik_masa_depan(warehouse_salinan)
    hari = trading_days(warehouse_salinan, AS_OF, 10)
    assert hari and max(hari) <= AS_OF
    assert max(hari) == date(2026, 9, 4), "as_of Sabtu — hari bursa terakhir Jumat"


@pytest.mark.parametrize("probe", SEMUA, ids=NAMA)
def test_bukti_tidak_pernah_bertanggal_setelah_as_of(probe, ctx):
    """EvidenceEntry.as_of menjawab 'kapan data ini berlaku'. Nilai setelah
    as_of berarti kita menampilkan sesuatu yang belum terjadi."""
    for symbol in ("FIXA", "FIXB", "FIXC", "FIXE"):
        for bukti in probe.run(symbol, ctx).evidence:
            assert bukti.as_of.date() <= AS_OF, f"{bukti.id} bertanggal {bukti.as_of}"
