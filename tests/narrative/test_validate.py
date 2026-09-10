"""Validator sitasi [AD-4]. Dua sisi diuji, dan sisi yang menolak diuji lebih keras.

Klaim "halusinasi angka secara struktural mustahil lolos" cuma sah kalau ada tes
yang benar-benar menyuapkan angka karangan dan melihatnya ditolak — bukan tes
yang memanggil validator pada kalimat bersih lalu menyatakan aman.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from contracts.schemas import EvidenceEntry
from core.narrative.validate import unsupported_numbers

ROOT = Path(__file__).resolve().parents[2]
WIB = timezone(timedelta(hours=7))


def bukti(id_: str, label: str, value, display: str, probe="broker_concentration") -> EvidenceEntry:
    return EvidenceEntry(
        id=id_, label=label, value=value, display=display, probe=probe,
        source_endpoint="fetch-broker-summary", source_params={"symbol": "FIXB"},
        source_transport="rest", as_of=datetime(2026, 9, 5, 17, 30, tzinfo=WIB),
        credits_spent=2,
    )


BUKU = [
    bukti("bci.top3_share", "Pangsa net buy 3 broker teratas", 0.78, "78%"),
    bukti("vas.zscore", "Z-score volume vs baseline 90 hari", 4.1, "4,1σ", "volume_anomaly"),
    bukti("pfd.return_90d", "Return 90 hari", 1.42, "+142%", "price_fundamental"),
    bukti("pfd.earnings_change", "Perubahan laba bersih year-on-year", -0.08, "-8%",
          "price_fundamental"),
    bukti("frd.foreign_net_30d", "Arus asing bersih 30 hari", -184000000000, "-Rp 184 M",
          "foreign_flow"),
    bukti("sss.prior_suspension", "Suspensi sebelumnya", "2025-11-14", "14 November 2025",
          "structural"),
    bukti("bci.hhi", "Indeks Herfindahl konsentrasi broker", 0.31, "0,31"),
]


# ── yang HARUS ditolak ──────────────────────────────────────────────────────
HALUSINASI = [
    # Angka yang sama sekali tidak ada di buku bukti.
    ("Volume berada 9,9σ di atas baseline 90 hari.", "9,9σ"),
    # Angka yang "masuk akal" tapi tidak pernah diukur — bentuk karangan paling
    # berbahaya, karena pembaca tidak punya cara membedakannya.
    ("Pangsa net buy 3 broker teratas mencapai 79%.", "79%"),
    # Angka benar, satuan digeser seribu kali.
    ("Asing keluar bersih Rp 184 T dalam 30 hari.", "184 T"),
    # Bilangan kecil yang dikarang. Tidak ada pemakluman untuk angka kecil.
    ("Tercatat 5 transaksi jual insider.", "5"),
    # Tanggal karangan.
    ("Emiten ini pernah disuspend pada 12 Maret 2024.", "12"),
    # Hasil hitungan sendiri: 78% dan 4,1σ ada, jumlahnya tidak.
    ("Gabungan kedua indikator setara 82,1 poin risiko.", "82,1"),
    # Angka berformat ribuan Indonesia yang tidak bersumber.
    ("Harga menyentuh 1.500 pada penutupan.", "1.500"),
]


@pytest.mark.parametrize(("narasi", "tersangka"), HALUSINASI)
def test_angka_karangan_ditolak(narasi, tersangka):
    hasil = unsupported_numbers(narasi, BUKU)
    assert hasil, f"halusinasi lolos validator: {narasi}"
    assert tersangka in hasil, f"yang ditunjuk salah: {hasil}"


def test_buku_bukti_dipalsukan_membuat_narasi_benar_jadi_ditolak():
    """Sisi sebaliknya: narasi tidak berubah, buku buktinya yang dikosongkan.

    Ini yang membuktikan validator benar-benar membaca buku bukti, bukan
    mengenali pola angka yang kebetulan tampak wajar.
    """
    narasi = "Pangsa net buy 3 broker teratas 78% dan volume 4,1σ di atas baseline."
    assert unsupported_numbers(narasi, BUKU) == []
    assert unsupported_numbers(narasi, []) == ["3", "78%", "4,1σ"]


def test_satu_angka_karangan_di_tengah_kalimat_benar_tetap_tertangkap():
    narasi = ("Pangsa net buy 3 broker teratas 78%, volume 4,1σ di atas baseline, "
              "dan asing keluar bersih Rp 900 M.")
    assert unsupported_numbers(narasi, BUKU) == ["900 M"]


# ── yang HARUS lolos ────────────────────────────────────────────────────────
BERSIH = [
    "Sebanyak 78% net buy dikuasai tiga broker.",             # bilangan sebagai kata
    "Volume berada 4,1σ di atas baseline 90 hari.",           # koma desimal + angka label
    "Harga naik 142% sementara laba bersih turun 8%.",        # tanda ada di display saja
    "Asing keluar bersih Rp 184 M dalam 30 hari terakhir.",   # rupiah berskala
    "Indeks Herfindahl tercatat 0,31.",
    "Emiten pernah disuspend pada 14 November 2025.",         # tanggal Indonesia
    "Arus asing bersih -184000000000 rupiah.",                # value mentah, bukan display
    "Pangsa net buy 3 broker teratas tetap dominan.",         # angka dari label
]


@pytest.mark.parametrize("narasi", BERSIH)
def test_narasi_bersumber_diloloskan(narasi):
    hasil = unsupported_numbers(narasi, BUKU)
    assert hasil == [], f"ditolak padahal bersumber: {narasi} -> {hasil}"


def test_narasi_tanpa_angka_selalu_lolos():
    assert unsupported_numbers("Tidak ada pola tidak biasa yang menonjol.", []) == []


@pytest.mark.parametrize("nama", ["normal", "waspada", "eskalasi"])
def test_fixture_beku_lolos_validator(nama):
    """Transkrip beku Nadhilla adalah kontrak tampilan. Validator yang menolaknya
    berarti validatornya yang salah, bukan fixture-nya."""
    data = json.loads((ROOT / "fixtures" / "transcripts" / f"{nama}.json").read_text("utf-8"))
    evidence = [EvidenceEntry.model_validate(e) for e in data["evidence"]]
    assert unsupported_numbers(data["narrative"], evidence) == []


def test_duplikat_dilaporkan_sekali():
    narasi = "Naik 55% pada pekan pertama, lalu 55% lagi pada pekan kedua."
    assert unsupported_numbers(narasi, BUKU) == ["55%"]
