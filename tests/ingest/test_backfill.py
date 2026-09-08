"""Perencanaan backfill. Semua tanpa jaringan — yang diuji rencananya, bukan tarikannya."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from core.ingest import backfill as bf
from core.ingest.warehouse import Warehouse
from core.sectors.ledger import CAPS

MINI = Path(__file__).resolve().parents[2] / "fixtures" / "warehouse-mini"
AS_OF = date(2026, 9, 5)


@pytest.fixture
def wh():
    return Warehouse(MINI)


def test_rencana_muat_di_pagu_fase(wh):
    """Rencana yang melebihi pagu berarti kredit habis sebelum kalibrasi selesai —
    risiko 'Fatal' di ARCHITECTURE §11."""
    total = (bf.plan_stage1(AS_OF).credits
             + bf.plan_stage2(AS_OF).credits
             + bf.plan_stage3(["FIXB", "FIXC"], AS_OF).credits)
    assert total <= CAPS["backfill"]


def test_tahap1_seratus_dua_puluh_hari_bursa():
    plan = bf.plan_stage1(AS_OF, sessions=120)
    assert len(plan.calls) == 120
    assert plan.credits == 120
    tanggal = [date.fromisoformat(p["date"]) for _, p in plan.calls]
    assert all(d.weekday() < 5 for d in tanggal), "akhir pekan tidak dipanggil"
    assert max(tanggal) <= AS_OF


def test_tahap2_dipecah_per_bulan():
    """Sekali tarik 24 bulan lebih sering timeout, dan gagal di tengah berarti
    kehilangan seluruh rentang. Per bulan juga kena cache saat diulang."""
    plan = bf.plan_stage2(AS_OF, bulan=24)
    suspensi = [p for n, p in plan.calls if n == "fetch-suspensions"]
    assert len(suspensi) == 25, "24 bulan penuh + bulan berjalan"
    assert all(p["start"] <= p["end"] for p in suspensi)
    assert max(p["end"] for p in suspensi) == AS_OF.isoformat()


def test_tahap3_menarik_enam_endpoint_per_ticker():
    plan = bf.plan_stage3(["FIXB"], AS_OF)
    assert {n for n, _ in plan.calls} == set(bf.TIER2_PER_TICKER)
    assert all("symbol" in p for _, p in plan.calls)


def test_biaya_per_ticker_wajar():
    """~11 kredit/ticker. Pagu 250 untuk tahap 3 berarti ±22 ticker; kalau
    biayanya naik diam-diam, cakupan kalibrasi menyusut tanpa ada yang sadar."""
    satu = bf.plan_stage3(["FIXB"], AS_OF).credits
    assert satu <= 12
    assert bf.plan_stage3(["FIXB", "FIXC"], AS_OF).credits == 2 * satu


# ── himpunan positif ────────────────────────────────────────────────────────
def test_positif_disaring_dari_alasan_resmi(wh):
    """Sumber label kalibrasi. FIXC disuspend karena 'pergerakan harga di luar
    kebiasaan'; FIXE karena menunggu keterbukaan informasi."""
    rows = bf.positives(wh, AS_OF)
    peta = {r["symbol"]: r for r in rows}

    assert peta["FIXC"]["is_positive"] is True
    assert peta["FIXC"]["matched_keywords"]
    assert peta["FIXE"]["is_positive"] is False


def test_alasan_resmi_ikut_diserahkan(wh):
    """Hamzah harus bisa memeriksa ulang penyaringannya sendiri — suspensi bukan
    sinonim manipulasi, dan batasan itu ditulis terbuka di halaman Metodologi."""
    for row in bf.positives(wh, AS_OF):
        assert set(row) == {"symbol", "start_date", "reason", "matched_keywords", "is_positive"}
        assert row["reason"], f"{row['symbol']} tanpa alasan resmi"


def test_positif_tidak_melihat_suspensi_masa_depan(tmp_path):
    wh = Warehouse(tmp_path)
    wh.write("suspensions", pd.DataFrame([
        {"symbol": "FIXX", "start_date": date(2026, 9, 20), "end_date": None,
         "reason": "Pergerakan harga di luar kebiasaan"}]))
    assert bf.positives(wh, AS_OF) == []


def test_kata_kunci_sinkron_dengan_probe_struktural():
    """Kalau daftarnya menyimpang, himpunan positif Hamzah dan skor SSS bicara
    tentang dua hal yang berbeda."""
    from core.probes.structural import ALASAN_TIDAK_WAJAR

    assert set(bf.ALASAN_POSITIF) <= set(ALASAN_TIDAK_WAJAR)


# ── kontrol ─────────────────────────────────────────────────────────────────
def test_kontrol_tersamakan_subsektor(tmp_path):
    """Kontrol acak bikin model belajar membedakan ukuran perusahaan dan
    terlihat hebat tanpa mendeteksi apa pun."""
    wh = Warehouse(tmp_path)
    wh.write("company_profile", pd.DataFrame([
        {"symbol": "POSI", "company_name": "P", "sub_sector": "energy",
         "market_cap": 1_000, "listing_date": date(2020, 1, 1)},
        {"symbol": "DEKA", "company_name": "D", "sub_sector": "energy",
         "market_cap": 1_100, "listing_date": date(2020, 1, 1)},
        {"symbol": "JAUH", "company_name": "J", "sub_sector": "energy",
         "market_cap": 900_000, "listing_date": date(2020, 1, 1)},
        {"symbol": "LAIN", "company_name": "L", "sub_sector": "banks",
         "market_cap": 1_050, "listing_date": date(2020, 1, 1)},
    ]))
    kontrol = bf.controls(wh, AS_OF, ["POSI"], per_positif=1)

    assert kontrol == ["DEKA"], "subsektor sama dan kapitalisasi terdekat"


def test_kontrol_tidak_memilih_positif_itu_sendiri(tmp_path):
    wh = Warehouse(tmp_path)
    wh.write("company_profile", pd.DataFrame([
        {"symbol": f"SYM{i}", "company_name": "x", "sub_sector": "energy",
         "market_cap": 1_000 + i, "listing_date": date(2020, 1, 1)} for i in range(4)]))
    positif = ["SYM0", "SYM1"]
    kontrol = bf.controls(wh, AS_OF, positif, per_positif=2)
    assert not set(kontrol) & set(positif)
    assert len(kontrol) == len(set(kontrol)), "satu emiten tidak dipakai dua kali"


# ── CLI ─────────────────────────────────────────────────────────────────────
def test_dry_run_tidak_menyentuh_apa_pun(capsys, monkeypatch, tmp_path):
    """Satu-satunya cara mengetahui ongkos sebelum membayarnya."""
    def jangan(*a, **k):
        raise AssertionError("dry-run tidak boleh membuat klien")

    monkeypatch.setattr(bf, "CreditAwareClient", jangan)
    kode = bf.main(["--dry-run", "--as-of", "2026-09-05", "--warehouse", str(MINI),
                    "--out", str(tmp_path)])

    keluaran = capsys.readouterr().out
    assert kode == 0
    assert "TAHAP 1" in keluaran and "TOTAL RENCANA" in keluaran
    assert "pagu fase backfill" in keluaran


def test_rencana_kelewat_besar_ditolak_lebih_dulu(capsys, tmp_path):
    """Lebih baik menolak di terminal daripada berhenti di tengah tarikan."""
    kode = bf.main(["--dry-run", "--as-of", "2026-09-05", "--sessions", "900",
                    "--warehouse", str(MINI), "--out", str(tmp_path)])
    assert kode == 2
    assert "melebihi sisa pagu" in capsys.readouterr().out
