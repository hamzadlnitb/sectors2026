"""Warehouse: skema dari kontrak, penggabungan, dan penyaringan point-in-time."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from core.ingest.warehouse import TABLES, Warehouse, columns_of, ddl_for, trading_days


def test_skema_diambil_dari_kontrak_bukan_ditulis_ulang():
    """Kalau contracts/warehouse.sql berubah, penulis ikut berubah sendiri."""
    assert columns_of("daily_close") == ["trade_date", "symbol", "close_price"]
    assert "PRIMARY KEY" in ddl_for("broker_summary")


def test_semua_tabel_kontrak_terdaftar():
    """investigations sengaja tidak ada di sini: itu memori agen, milik Hamzah."""
    import re

    from core.ingest.warehouse import DDL_PATH

    di_ddl = set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)",
                            DDL_PATH.read_text(encoding="utf-8")))
    assert set(TABLES) == di_ddl - {"investigations"}


def test_tabel_tak_dikenal_gagal_jelas():
    with pytest.raises(KeyError, match="warehouse.sql"):
        ddl_for("tabel_karangan")


# ── penggabungan ────────────────────────────────────────────────────────────
def test_tulis_ulang_idempoten(tmp_path):
    wh = Warehouse(tmp_path)
    df = pd.DataFrame([{"trade_date": date(2026, 9, 4), "symbol": "FIXA", "close_price": 100.0}])
    assert wh.write("daily_close", df) == 1
    assert wh.write("daily_close", df) == 1, "backfill dua kali menggandakan baris"


def test_baris_baru_menang_atas_yang_lama(tmp_path):
    """Tarikan ulang memperbaiki data basi, bukan menumpuk dua kebenaran."""
    wh = Warehouse(tmp_path)
    kunci = {"trade_date": date(2026, 9, 4), "symbol": "FIXA"}
    wh.write("daily_close", pd.DataFrame([{**kunci, "close_price": 100.0}]))
    wh.write("daily_close", pd.DataFrame([{**kunci, "close_price": 111.0}]))

    df = wh.frame("daily_close")
    assert len(df) == 1
    assert df["close_price"].iloc[0] == 111.0


def test_tabel_tanpa_kunci_primer_tetap_dideduplikasi(tmp_path):
    """filings tidak punya PK di DDL. Tanpa dedup eksplisit, menjalankan
    backfill dua kali akan menggandakan tiap filing."""
    wh = Warehouse(tmp_path)
    baris = pd.DataFrame([{
        "filing_date": date(2026, 8, 3), "symbol": "FIXB", "holder_name": "X",
        "holder_type": "insider", "transaction_type": "sell", "shares": 1000, "price": 10.0,
    }])
    wh.write("filings", baris)
    assert wh.write("filings", baris) == 1


def test_free_float_menyimpan_riwayat_bukan_menimpanya(tmp_path):
    """PK kontrak cuma (symbol), yang berarti satu snapshot per emiten dan
    riwayat hilang. Penggabungan memakai (symbol, as_of) — contracts/CHANGES.md C4.

    Tanpa ini, FFS pada T-1/T-3/T-5/T-10 terpaksa memakai angka hari ini, dan
    kalibrasi bobot Hamzah bocor lookahead."""
    wh = Warehouse(tmp_path)
    wh.write("free_float", pd.DataFrame([
        {"symbol": "FIXC", "free_float_pct": 0.12, "as_of": date(2026, 3, 31)}]))
    wh.write("free_float", pd.DataFrame([
        {"symbol": "FIXC", "free_float_pct": 0.04, "as_of": date(2026, 6, 30)}]))

    assert len(wh.frame("free_float")) == 2
    lama = wh.frame("free_float", as_of=date(2026, 5, 1))
    assert len(lama) == 1 and lama["free_float_pct"].iloc[0] == 0.12


# ── point-in-time ───────────────────────────────────────────────────────────
def test_view_menyaring_tanggal_setelah_as_of(tmp_path):
    wh = Warehouse(tmp_path)
    wh.write("daily_close", pd.DataFrame([
        {"trade_date": date(2026, 9, 4), "symbol": "FIXA", "close_price": 100.0},
        {"trade_date": date(2026, 9, 8), "symbol": "FIXA", "close_price": 999.0},
    ]))
    assert len(wh.frame("daily_close", as_of=date(2026, 9, 5))) == 1
    assert len(wh.frame("daily_close")) == 2, "tanpa as_of, ingest tetap melihat semuanya"


def test_company_profile_tanpa_tanggal_listing_tetap_lolos(tmp_path):
    """Tabel identitas: nama emiten dan subsektor tidak membocorkan hasil.
    Membuangnya berarti probe tidak bisa mengenali emiten sama sekali."""
    wh = Warehouse(tmp_path)
    wh.write("company_profile", pd.DataFrame([
        {"symbol": "FIXA", "company_name": "Fiksi A", "sub_sector": "banks",
         "market_cap": 10**12, "listing_date": None}]))
    assert len(wh.frame("company_profile", as_of=date(2020, 1, 1))) == 1


def test_tabel_belum_ada_memberi_nol_baris_bukan_error(tmp_path):
    """Probe menanyakan tabel yang belum diisi; itu bukan alasan meledak."""
    wh = Warehouse(tmp_path)
    df = wh.frame("broker_summary", as_of=date(2026, 9, 5))
    assert df.empty
    assert list(df.columns) == columns_of("broker_summary")


def test_hari_bursa_dari_data_bukan_dari_kalender(tmp_path):
    """Libur nasional IDX tidak bisa ditebak dari hari kerja."""
    wh = Warehouse(tmp_path)
    hari = [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 4)]  # 3 Sep libur
    wh.write("daily_close", pd.DataFrame([
        {"trade_date": d, "symbol": "FIXA", "close_price": 100.0} for d in hari]))

    assert trading_days(wh, date(2026, 9, 5), 10) == hari
    assert trading_days(wh, date(2026, 9, 5), 2) == hari[-2:]


def test_ringkasan_menyebut_tabel_kosong(tmp_path):
    wh = Warehouse(tmp_path)
    ringkas = {r["table"]: r["rows"] for r in wh.summary()}
    assert set(ringkas) == set(TABLES)
    assert all(v == 0 for v in ringkas.values())
