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


ALAM_SEMESTA = [f"T{i:03d}" for i in range(80)]


def test_free_float_tidak_ditarik_per_emiten():
    """1 kredit per 100 emiten dan bisa market-wide: menariknya per emiten berarti
    membayar 1 kredit untuk satu baris yang sudah termasuk tarikan market-wide."""
    assert "fetch-free-float" not in bf.TIER2_PER_TICKER
    assert any(e == "fetch-free-float" for e, _, _ in bf.MARKET_WIDE)


def test_rencana_produksi_muat_di_pagu_fase():
    """80 ticker riwayat + peristiwa + Tier-2 untuk 20 ticker harus muat di 400.

    Versi pertama rencana ini menarik fetch-close sekali per hari bursa dan
    menghabiskan ~3.840 kredit — hampir empat kali seluruh jatah tim, untuk satu
    tahap saja. Tes ini yang menahannya kalau ada yang mengembalikannya."""
    total = (bf.plan_stage1(AS_OF, ALAM_SEMESTA[:60]).credits
             + bf.plan_stage2(AS_OF).credits
             + bf.plan_stage3(ALAM_SEMESTA[:20], AS_OF).credits)
    assert total <= CAPS["backfill"], f"rencana {total} kredit melebihi pagu"


def test_tahap1_per_ticker_bukan_per_hari():
    """fetch-close berbayar 1 kredit PER HALAMAN (~32 halaman untuk seluruh IDX),
    jadi menariknya sekali per hari bursa mustahil dibiayai. fetch-daily-transaction
    memberi rentang sampai 90 hari dengan 1 kredit."""
    plan = bf.plan_stage1(AS_OF, ["BBCA", "GOTO"], sessions=120)

    assert {n for n, _ in plan.calls} == {"fetch-daily-transaction"}
    assert plan.credits == 4, "2 ticker x 2 jendela 90 hari"
    for _, params in plan.calls:
        assert params["end"] <= AS_OF.isoformat(), "tidak menarik masa depan"


def test_tahap1_menutup_seluruh_rentang_yang_diminta():
    plan = bf.plan_stage1(AS_OF, ["BBCA"], sessions=120)
    paling_awal = min(date.fromisoformat(p["start"]) for _, p in plan.calls)
    assert (AS_OF - paling_awal).days >= 120


def test_alam_semesta_dipersempit_tanpa_kredit(wh):
    """Penyempitan diambil dari warehouse, bukan dari panggilan baru. Emiten yang
    pernah disuspend WAJIB ikut — mereka himpunan positifnya."""
    u = bf.universe(wh, AS_OF, size=10)
    assert "FIXC" in u and "FIXE" in u, "ticker tersuspend wajib masuk alam semesta"
    assert len(u) <= 10


def test_tahap2_menelusuri_halaman_bukan_memecah_bulan():
    """Spike F0: fetch-suspensions melaporkan total_count 533 tapi satu panggilan
    cuma mengirim 20 baris. Rencana per-bulan yang lama akan menarik 25 potong
    berisi 20 baris PERTAMA masing-masing, lalu mengira 24 bulan sudah lengkap."""
    plan = bf.plan_stage2(AS_OF, bulan=24)
    suspensi = [p for n, p in plan.calls if n == "fetch-suspensions"]

    # 534 baris pada ~30 baris per halaman = 18 panggilan. Diukur, bukan ditebak:
    # tarikan sungguhan 8 Sep mengambil 534 suspensi dalam 18 panggilan.
    assert len(suspensi) == 18
    assert all(p["limit"] == bf.PAGE_SIZE for p in suspensi)
    # Satu rentang penuh, bukan 25 jendela sempit.
    assert len({(p["start"], p["end"]) for p in suspensi}) == 1
    assert max(p["end"] for p in suspensi) == AS_OF.isoformat()


def test_tahap2_dibatasi_pagu_kredit_per_endpoint():
    """Pagar halaman tidak tahu harga. fetch-filings pernah menembus 50 halaman
    = 50 kredit untuk anggaran 3, lalu kena 429 dan hasilnya hangus."""
    plan = bf.plan_stage2(AS_OF)
    per_endpoint: dict[str, int] = {}
    for nama, _ in plan.calls:
        per_endpoint[nama] = per_endpoint.get(nama, 0) + 1
    for nama, jumlah in per_endpoint.items():
        assert jumlah <= bf.PAGU_HALAMAN[nama], f"{nama} melewati pagunya sendiri"


def test_perkiraan_halaman_pakai_ukuran_server_bukan_permintaan_kita():
    """Sectors memangkas limit 100 jadi ~30. Menghitung dengan 100 membuat
    rencana meleset 3x — persis yang bikin tahap 2 habis 68 kredit dari 9."""
    assert bf.PAGE_SIZE_NYATA < bf.PAGE_SIZE
    assert bf._perkiraan_halaman(534) == 18


def test_tahap3_menarik_enam_endpoint_per_ticker():
    plan = bf.plan_stage3(["FIXB"], AS_OF)
    assert {n for n, _ in plan.calls} == set(bf.TIER2_PER_TICKER)
    assert all("symbol" in p for _, p in plan.calls)


def test_biaya_per_ticker_wajar():
    """Biaya per emiten menentukan besar sampel kalibrasi: tiap kenaikan 1 kredit
    memotong sampel. Kalau naik diam-diam, cakupan menyusut tanpa ada yang sadar."""
    satu = bf.plan_stage3(["FIXB"], AS_OF).credits
    assert satu == 13, "profil 2 + filings 1 + harga 1 + broker 2 + asing 1 + kuartal 5 + aksi 1"
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
    banyak = [f"T{i:03d}" for i in range(200)]
    kode = bf.main(["--dry-run", "--as-of", "2026-09-05", "--sessions", "900",
                    "--symbols", *banyak,
                    "--warehouse", str(MINI), "--out", str(tmp_path)])
    assert kode == 2
    assert "melebihi sisa pagu" in capsys.readouterr().out
