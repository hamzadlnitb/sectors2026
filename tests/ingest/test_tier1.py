"""Sapuan Tier-1 dan penyaringan kandidat. Nol jaringan."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from core.ingest import tier1_market as t1
from core.ingest.warehouse import Warehouse
from core.sectors.client import CreditAwareClient
from core.sectors.errors import TransportAttemptError
from core.sectors.ledger import CreditLedger
from core.sectors.routing import TIER1_SWEEP, cost_of

MINI = Path(__file__).resolve().parents[2] / "fixtures" / "warehouse-mini"
AS_OF = date(2026, 9, 5)


class FakeSweepTransport:
    """Mengembalikan payload masuk akal untuk tiap endpoint Tier-1."""

    name = "rest"

    def __init__(self, gagal: set[str] | None = None):
        self.gagal = gagal or set()
        self.calls: list[str] = []

    def fetch(self, endpoint, params):
        self.calls.append(endpoint.name)
        if endpoint.name in self.gagal:
            raise TransportAttemptError("server ngambek", retryable=False, status=500)
        hari = params.get("date") or params.get("end") or "2026-09-08"
        return {
            "fetch-close": [{"symbol": "FIXA", "date": hari, "close": 9700.0},
                            {"symbol": "FIXB", "date": hari, "close": 1400.0}],
            "fetch-most-traded-stocks": [{"symbol": "FIXB", "date": hari,
                                          "volume": 26_000_000, "price": 1400.0}],
            "fetch-companies-top-changes": [{"symbol": "FIXC", "price_change": 0.24,
                                             "last_close": 215.0}],
            "fetch-suspensions": [{"symbol": "FIXE", "start_date": hari,
                                   "reason": "Menunggu keterbukaan informasi"}],
            "fetch-filings": [{"symbol": "FIXB", "date": hari, "holder": "Direktur",
                               "transaction_type": "sell", "shares": 5_000_000}],
        }[endpoint.name]

    def close(self):
        pass


@pytest.fixture
def wh(tmp_path):
    """Salinan warehouse-mini yang boleh ditulisi."""
    import shutil

    tujuan = tmp_path / "wh"
    shutil.copytree(MINI, tujuan, ignore=shutil.ignore_patterns("*.md", "*.py"))
    return Warehouse(tujuan)


def buat_client(tmp_path, ledger, transport):
    return CreditAwareClient(api_key="k" * 20, phase="daily", ledger=ledger,
                             cache_dir=tmp_path / "cache", rest=transport,
                             sleep=lambda _: None)


# ── anggaran ────────────────────────────────────────────────────────────────
def test_fetch_close_tidak_ikut_sapuan_harian():
    """Katalog MCP: 1 kredit PER HALAMAN, ~32 halaman untuk seluruh IDX. Ikut
    sapuan harian berarti 800 kredit untuk 25 hari bursa — pagu operasinya 250."""
    assert "fetch-close" not in TIER1_SWEEP
    assert sum(cost_of(e) for e in TIER1_SWEEP) * 25 <= 250


def test_sapuan_harian_tetap_di_bawah_enam_kredit(tmp_path, wh):
    """250 kredit operasi dibagi 25 hari = 10/hari untuk sapuan DAN agen.
    Sapuan yang membengkak berarti agen tidak kebagian."""
    ledger = CreditLedger(tmp_path / "l.jsonl")
    hasil = t1.sweep(buat_client(tmp_path, ledger, FakeSweepTransport()), wh, AS_OF)

    assert hasil.credits_spent == sum(cost_of(e) for e in TIER1_SWEEP)
    assert hasil.credits_spent <= 6, "sapuan harian tidak boleh membengkak"
    assert hasil.ok


def test_endpoint_gagal_tidak_menghentikan_sisanya(tmp_path, wh):
    """Data separuh lebih berguna daripada tidak ada — tapi kegagalannya tetap
    dilaporkan supaya workflow jadi merah, bukan diam. [QA M4]"""
    ledger = CreditLedger(tmp_path / "l.jsonl")
    transport = FakeSweepTransport(gagal={"fetch-suspensions"})
    hasil = t1.sweep(buat_client(tmp_path, ledger, transport), wh, AS_OF)

    assert not hasil.ok
    assert len(hasil.failures) == 1 and "fetch-suspensions" in hasil.failures[0]
    assert len(hasil.rows_written) == 3, "endpoint lain tetap jalan"


def test_offline_dilewati_bukan_digagalkan(tmp_path, wh):
    """Mode offline adalah keadaan yang diminta, bukan kegagalan."""
    ledger = CreditLedger(tmp_path / "l.jsonl")
    client = CreditAwareClient(offline=True, ledger=ledger, cache_dir=tmp_path / "c")
    hasil = t1.sweep(client, wh, AS_OF)

    assert hasil.ok
    assert len(hasil.skipped) == len(TIER1_SWEEP)
    assert hasil.credits_spent == 0


def test_sapuan_kedua_dilayani_cache(tmp_path, wh):
    ledger = CreditLedger(tmp_path / "l.jsonl")
    transport = FakeSweepTransport()
    client = buat_client(tmp_path, ledger, transport)

    pertama = t1.sweep(client, wh, AS_OF)
    kedua = t1.sweep(client, wh, AS_OF)

    assert kedua.credits_spent == 0
    assert ledger.spent("daily") == pertama.credits_spent, (
        "cron yang diulang hari sama tidak membayar lagi"
    )


def test_baris_dipetakan_ke_tabel_yang_benar(tmp_path, wh):
    """most-traded -> daily_transaction, top-changes -> daily_close.
    Bentuk barisnya memang cocok, jadi tidak perlu tabel baru di kontrak."""
    ledger = CreditLedger(tmp_path / "l.jsonl")
    t1.sweep(buat_client(tmp_path, ledger, FakeSweepTransport()), wh, AS_OF)

    trans = wh.frame("daily_transaction")
    assert not trans[(trans["symbol"] == "FIXB") & (trans["volume"] == 26_000_000)].empty
    close = wh.frame("daily_close")
    assert "FIXC" in close["symbol"].tolist()


# ── penyaringan kandidat ────────────────────────────────────────────────────
def test_penyaringan_tidak_menghabiskan_kredit(wh, tmp_path):
    """Kalau penyaringannya sendiri berbayar, seluruh alasan keberadaan agen
    (menghemat kredit) runtuh."""
    ledger = CreditLedger(tmp_path / "l.jsonl")
    t1.screen(wh, AS_OF)
    assert ledger.spent("daily") == 0


def test_kandidat_terurut_dari_yang_paling_layak(wh):
    kandidat = t1.screen(wh, AS_OF)
    assert kandidat, "warehouse-mini seharusnya menghasilkan kandidat"
    assert kandidat[0]["symbol"] == "FIXC", "float 4% + volume ekstrem harus di puncak"
    skor = [c["score"] for c in kandidat]
    assert skor == sorted(skor, reverse=True)


def test_tiap_kandidat_membawa_alasan_yang_bisa_dibaca(wh):
    for c in t1.screen(wh, AS_OF):
        assert c["alasan"], f"{c['symbol']} tanpa alasan"
        assert set(c["signals"]) == set(t1.BOBOT)


def test_penyaringan_tidak_melihat_masa_depan(wh):
    """warehouse-mini memuat baris setelah as_of sebagai umpan."""
    sebelum = t1.screen(wh, AS_OF)
    wh.write("daily_close", pd.DataFrame([
        {"trade_date": date(2026, 9, 30), "symbol": "FIXA", "close_price": 999_999.0}]))
    assert t1.screen(wh, AS_OF) == sebelum


def test_warehouse_kosong_memberi_daftar_kosong(tmp_path):
    assert t1.screen(Warehouse(tmp_path), AS_OF) == []


# ── normalisasi & sesi — AUDIT B2, B3 ───────────────────────────────────────
@pytest.mark.parametrize("nama", sorted(t1.PENUH))
def test_normalisasi_monoton_per_sinyal(nama):
    """Regresi B2: `_clip` lama memberi 1,5σ = 1,0 tapi 3σ = 0,5 — fungsi yang
    memilih emiten mana yang diselidiki agen tiap hari tidak monoton."""
    nilai = [-1.0, 0.0, 0.1, 0.3, 0.6, 1.0, 1.4, 1.5, 1.6, 3.0, 6.0, 10.0, 100.0]
    hasil = [t1._norm(nama, v) for v in nilai]
    assert hasil == sorted(hasil)
    assert all(0.0 <= h <= 1.0 for h in hasil)
    assert t1._norm(nama, None) == 0.0


def test_volume_3_sigma_di_atas_1_5_sigma():
    assert t1._norm("volume_z", 3.0) > t1._norm("volume_z", 1.5)


HARI_KERJA = [d.date() for d in pd.bdate_range("2026-08-03", "2026-09-11")]  # 30 sesi
AS_OF_SESI = HARI_KERJA[-1]


def _deret(sym, hari, harga=None, lonjakan=False):
    """Deret harian dengan volume yang bervariasi (MAD > 0); `lonjakan` membuat
    baris terakhirnya melonjak."""
    baris = [{"trade_date": d, "symbol": sym, "close_price": (harga or {}).get(d, 100.0),
              "volume": 1_000_000 + (i % 5) * 100_000, "market_cap": None}
             for i, d in enumerate(hari)]
    if lonjakan:
        baris[-1]["volume"] = 50_000_000
    return baris


@pytest.fixture
def wh_sesi(tmp_path):
    """REF terisi tiap sesi, jadi kalender bursa warehouse lengkap 30 sesi."""
    wh = Warehouse(tmp_path / "sesi")
    wh.write("daily_transaction", pd.DataFrame(_deret("REF", HARI_KERJA)))
    return wh


def _kandidat(wh, sym):
    return next((c for c in t1.screen(wh, AS_OF_SESI, size=100) if c["symbol"] == sym), None)


def test_return_dihitung_atas_sesi_bukan_baris(wh_sesi):
    """Regresi B3, bentuk PACK: riwayat lalu lompat ke hari acuan. Dulu baris
    ke-6 dari belakang dianggap "5 hari lalu", padahal berminggu-minggu."""
    hari = HARI_KERJA[:22] + [AS_OF_SESI]
    wh_sesi.write("daily_transaction",
                  pd.DataFrame(_deret("LOMPAT", hari, {AS_OF_SESI: 200.0})))
    c = _kandidat(wh_sesi, "LOMPAT")

    assert c["signals"]["return_5d"] is None, "5 sesi terakhir kosong — tidak tersedia"
    assert c["signals"]["return_20d"] == pytest.approx(1.0), \
        "kedua ujung 20 sesi ada di sesi yang tepat, jadi return-nya sah"


def test_return_5d_none_bila_enam_sesi_terakhir_berlubang(wh_sesi):
    hari = [d for d in HARI_KERJA if d != HARI_KERJA[-3]]
    wh_sesi.write("daily_transaction", pd.DataFrame(_deret("BOLONG", hari)))
    assert _kandidat(wh_sesi, "BOLONG")["signals"]["return_5d"] is None


def test_return_5d_utuh_dihitung_benar(wh_sesi):
    harga = {HARI_KERJA[-6]: 100.0, AS_OF_SESI: 130.0}
    wh_sesi.write("daily_transaction", pd.DataFrame(_deret("UTUH", HARI_KERJA, harga)))
    assert _kandidat(wh_sesi, "UTUH")["signals"]["return_5d"] == pytest.approx(0.30)


def test_emiten_dengan_riwayat_pendek_tidak_diranking(wh_sesi):
    """Dua-tiga baris dari most-traded bukan riwayat untuk dinilai."""
    wh_sesi.write("daily_transaction", pd.DataFrame(_deret("PENDEK", HARI_KERJA[-5:])))
    assert _kandidat(wh_sesi, "PENDEK") is None


def test_lonjakan_volume_lama_bukan_sinyal_hari_ini(wh_sesi):
    """Baris terakhir FOSIL 10 sesi lalu. Tanpa batas kesegaran, lonjakan itu
    mendorongnya ke atas watchlist setiap hari sampai ada yang menarik datanya
    lagi — persis emiten 7 Sep yang bertahan di watchlist berminggu-minggu."""
    wh_sesi.write("daily_transaction", pd.DataFrame(
        _deret("FOSIL", HARI_KERJA[:-10], lonjakan=True)
        + _deret("SEGAR", HARI_KERJA, lonjakan=True)))
    fosil, segar = _kandidat(wh_sesi, "FOSIL"), _kandidat(wh_sesi, "SEGAR")

    assert fosil["signals"]["volume_z"] is None
    assert segar["signals"]["volume_z"] > 6
    assert segar["score"] > fosil["score"]


# ── artefak run ─────────────────────────────────────────────────────────────
def test_artefak_run_lengkap_dan_bisa_diurai(tmp_path, wh):
    ledger = CreditLedger(tmp_path / "l.jsonl")
    hasil = t1.sweep(buat_client(tmp_path, ledger, FakeSweepTransport()), wh, AS_OF)
    hasil.candidates = t1.screen(wh, AS_OF)

    run_dir = tmp_path / "runs" / "2026-09-05"
    t1.write_run(run_dir, hasil)

    log = (run_dir / "run.log").read_text(encoding="utf-8")
    assert "sapuan Tier-1" in log and "Z]" in log, "log wajib ber-timestamp — itu buktinya [T5]"

    watchlist = json.loads((run_dir / "watchlist.json").read_text(encoding="utf-8"))
    assert watchlist["as_of"] == "2026-09-05"
    assert watchlist["credits_spent"] == hasil.credits_spent
    assert watchlist["candidates"][0]["symbol"] == "FIXC"
    assert watchlist["failures"] == []
