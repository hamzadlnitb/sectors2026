"""Model respons diuji atas RESPONS SECTORS SUNGGUHAN dari spike F0.

Ini tes paling berharga di repo, dan yang paling murah: `spikes/raw/*.json`
adalah tarikan asli 8 Sep 2026 yang sudah dibayar 9 kredit dan di-commit. Selama
berkas itu ada, seluruh lapisan parsing bisa diuji ulang **selamanya, gratis,
tanpa jaringan**.

Sebelum tes ini ada, empat dari tujuh endpoint diam-diam salah baca — bukan
error, tapi hasil kosong atau menumpuk di satu tanggal. Yang begitu tidak
ketahuan sampai kalibrasi memberi angka aneh dua minggu kemudian.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.sectors.schemas import flatten, pagination_of, parse_rows

RAW = Path(__file__).resolve().parents[2] / "spikes" / "raw"
BERKAS = sorted(RAW.glob("*.json"))
NAMA = [p.stem for p in BERKAS]


def payload(endpoint: str):
    return json.loads((RAW / f"{endpoint}.json").read_text(encoding="utf-8"))["payload"]


def test_spike_ter_commit():
    """Kalau berkasnya hilang, seluruh tes di bawah diam-diam jadi kosong."""
    assert len(BERKAS) == 7, f"harusnya 7 respons spike, ada {len(BERKAS)}"


@pytest.mark.parametrize("endpoint", NAMA)
def test_respons_asli_lolos_model(endpoint):
    rows = parse_rows(endpoint, payload(endpoint))
    assert rows, f"{endpoint} terurai jadi nol baris"


@pytest.mark.parametrize("endpoint", NAMA)
def test_ticker_ternormalisasi_tanpa_sufiks_jk(endpoint):
    """API mengembalikan 'ASLI.JK'; kontrak tim mematok ^[A-Z]{4}$. [C1 #5]"""
    for row in parse_rows(endpoint, payload(endpoint)):
        symbol = getattr(row, "symbol", None)
        if symbol is not None:
            assert ".JK" not in symbol and len(symbol) == 4, symbol


# ── bentuk yang dulunya salah baca ──────────────────────────────────────────
def test_arus_asing_mewarisi_symbol_dari_pembungkus():
    """Barisnya cuma {date, net_foreign_inflow}; symbol-nya ada sekali di atas.
    Tanpa penurunan konteks, tiap baris kehilangan identitas emitennya."""
    rows = parse_rows("fetch-foreign-flow", payload("fetch-foreign-flow"))
    assert all(r.symbol == "BBCA" for r in rows)
    assert any(r.net_value and r.net_value > 0 for r in rows), "net_foreign_inflow tidak terbaca"
    assert any(r.net_value and r.net_value < 0 for r in rows), "arus keluar hilang tandanya"


def test_most_traded_menurunkan_tanggal_dari_kunci():
    """Payloadnya dict berkunci tanggal. Kalau tanggalnya tidak diturunkan,
    seluruh riwayat menumpuk di satu hari dan z-score volume jadi omong kosong."""
    rows = parse_rows("fetch-most-traded-stocks", payload("fetch-most-traded-stocks"))
    tanggal = {r.trade_date for r in rows}
    assert len(tanggal) > 5, f"cuma {len(tanggal)} tanggal berbeda — tanggal tidak diturunkan"
    assert all(r.trade_date is not None for r in rows)


def test_top_changes_dirat_akan_dengan_arahnya():
    """Bersarang top_gainers/top_losers per periode. Arahnya wajib ikut terbawa —
    penyaring kandidat perlu membedakan yang naik dari yang turun."""
    rows = parse_rows("fetch-companies-top-changes", payload("fetch-companies-top-changes"))
    arah = {r.direction for r in rows}
    assert arah == {"top_gainers", "top_losers"}
    naik = [r for r in rows if r.direction == "top_gainers"]
    assert all(r.price_change and r.price_change > 0 for r in naik)
    assert all(r.last_close is not None for r in rows), "last_close_price tidak terbaca"


def test_laporan_emiten_diringkas_jadi_satu_baris_profil():
    """Laporan aslinya 100 KB bersarang; warehouse cuma butuh lima kolom."""
    rows = parse_rows("fetch-company-report", payload("fetch-company-report"))
    assert len(rows) == 1
    profil = rows[0]
    assert profil.symbol == "BBCA"
    assert profil.company_name and profil.sub_sector


def test_filing_stempel_waktu_dipotong_jadi_tanggal():
    """API mengirim '2026-09-07T19:36:14' untuk field bertipe DATE. Membiarkannya
    berarti tiap filing ditolak validator dan probe SSS kehilangan sinyal insider."""
    rows = parse_rows("fetch-filings", payload("fetch-filings"))
    assert all(r.filing_date is not None for r in rows)
    jual = [r for r in rows if r.transaction_type == "sell"]
    assert jual, "tidak ada transaksi jual terbaca — probe SSS akan selalu nol"
    assert all(r.holder_type for r in jual)


def test_suspensi_membawa_alasan_resmi():
    """Sumber label kalibrasi Hamzah. Tanpa alasan, himpunan positif tidak bisa disaring."""
    rows = parse_rows("fetch-suspensions", payload("fetch-suspensions"))
    assert all(r.reason for r in rows)
    from core.ingest.backfill import ALASAN_POSITIF

    cocok = [r for r in rows if any(k in (r.reason or "").lower() for k in ALASAN_POSITIF)]
    assert cocok, "nol suspensi cocok kata kunci — penyaring himpunan positif tidak berfungsi"


# ── paginasi: temuan anggaran ───────────────────────────────────────────────
@pytest.mark.parametrize("endpoint", ["fetch-suspensions", "fetch-filings"])
def test_paginasi_terbaca(endpoint):
    """20 baris per panggilan dari ratusan. Backfill yang mengabaikan ini akan
    mengira sudah menarik 24 bulan padahal baru satu halaman."""
    blok = pagination_of(payload(endpoint))
    assert blok is not None, f"{endpoint} punya paginasi tapi tidak terbaca"
    assert blok["total_count"] > blok["showing"], "sampel spike harusnya terpotong"
    assert blok["has_next"] is True


def test_endpoint_tanpa_paginasi_mengembalikan_none():
    assert pagination_of(payload("fetch-daily-transaction")) is None


def test_flatten_tidak_pernah_melempar():
    """Bentuk tak terduga jadi daftar kosong, bukan exception — pesan galat yang
    berguna datang dari parse_rows, bukan dari adapter."""
    for endpoint in ("fetch-most-traded-stocks", "fetch-companies-top-changes",
                     "fetch-company-report"):
        assert flatten(endpoint, None) == []
        assert flatten(endpoint, []) == []
