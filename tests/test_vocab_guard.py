"""Larangan kosakata [K5]. Dua sisi diuji, bukan satu.

Penjaga yang cuma diuji pada kalimat terlarang akan lolos walau ia menolak
segalanya. Yang menolak segalanya akan dimatikan orang dalam seminggu, dan
setelah itu tidak menjaga apa pun. Jadi: yang harus ditolak DAN yang harus
diloloskan.
"""

from __future__ import annotations

import json

import pytest

from tools.vocab_guard import DISCLAIMER, main, periksa_json, periksa_teks

HARUS_DITOLAK = [
    "Saham ini layak beli di harga sekarang.",
    "Target harga 1.500 dalam tiga bulan.",
    "Rekomendasi kami: tahan sampai kuartal depan.",
    "Potensi cuan besar pekan ini.",
    "Saham ini pasti naik setelah rights issue.",
    "Belilah selagi murah.",
    "Segera jual sebelum harganya turun.",
    "Sesuaikan portofolio Anda dengan temuan ini.",
    "Ini saran investasi dari analis kami.",
    "Beli sekarang.",
]

HARUS_LOLOS = [
    # Deskripsi faktual — ini yang harus tetap boleh ditulis.
    "Tercatat 3 transaksi jual insider dalam 90 hari terakhir.",
    "Pangsa net buy 3 broker teratas mencapai 78%.",
    "Aksi jual asing berlanjut selama sebelas hari bursa.",
    "Tekanan beli terkonsentrasi di dua broker.",
    "Asing keluar bersih Rp 184 M; nilai jual bersih naik.",
    "Volume berada 4,1σ di atas baseline 90 hari.",
    "Banyak indikator menunjukkan pola tidak biasa secara bersamaan.",
    "Free float 4% membuat saham mudah digerakkan segelintir pihak.",
    DISCLAIMER,
]


@pytest.mark.parametrize("kalimat", HARUS_DITOLAK)
def test_kalimat_saran_ditolak(kalimat):
    assert periksa_teks(kalimat), f"lolos padahal harus ditolak: {kalimat}"


@pytest.mark.parametrize("kalimat", HARUS_LOLOS)
def test_deskripsi_faktual_diloloskan(kalimat):
    hasil = periksa_teks(kalimat)
    assert not hasil, f"ditolak padahal deskripsi faktual: {kalimat} -> {hasil}"


def test_disclaimer_dikecualikan_sebagai_teks_utuh():
    """Bukan sebagai kata: kalimat yang mengaku memberi saran tetap ditolak."""
    assert not periksa_teks(f"Skor 74. {DISCLAIMER}")
    assert periksa_teks("Ini saran investasi yang bagus untuk pemula.")


def test_kata_inggris_tidak_ikut_dilarang():
    """buy/sell nama kolom data. Melarangnya = melarang menyebut datanya sendiri."""
    assert not periksa_teks("kolom buy_value dan sell_value dijumlahkan per broker")


def test_transkrip_beku_tetap_lolos():
    """fixtures/transcripts/waspada.json memuat 'transaksi jual insider'.
    Kalau penjaga menolaknya, yang salah penjaganya."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for path in (root / "fixtures" / "transcripts").glob("*.json"):
        assert periksa_json(path) == [], f"{path.name} ditolak penjaga kosakata"


def test_narasi_llm_tersimpan_ikut_diperiksa(tmp_path):
    """Ini justru berkas yang paling perlu dijaga: narasi ditulis LLM, dan
    prompt bisa diabaikan sementara CI tidak."""
    transkrip = tmp_path / "BBCA-2026-09-05.json"
    transkrip.write_text(json.dumps({
        "symbol": "BBCA",
        "narrative": "Skor tinggi. Rekomendasi kami: kurangi posisi.",
        "steps": [{"reason": "volume 4σ di atas baseline"}],
    }), encoding="utf-8")

    pelanggaran = periksa_json(transkrip)
    assert len(pelanggaran) == 1
    assert pelanggaran[0].lokasi == "$.narrative"


def test_repo_bersih():
    """Penjaga dijalankan atas repo apa adanya — ini bentuk yang dipakai CI."""
    assert main([]) == 0


def test_penanda_pengecualian_butuh_alasan(tmp_path):
    """'# vocab-ok' telanjang tidak cukup: pengecualian tanpa alasan akan
    ditempel ke mana-mana dan penjaga berhenti berarti."""
    from tools.vocab_guard import periksa_python

    tanpa = tmp_path / "tanpa.py"
    tanpa.write_text('pola = "sell|jual"  # vocab-ok\n', encoding="utf-8")
    assert periksa_python(tanpa), "pengecualian tanpa alasan seharusnya tidak berlaku"

    dengan = tmp_path / "dengan.py"
    dengan.write_text('pola = "sell|jual"  # vocab-ok: pola pencocok data\n', encoding="utf-8")
    assert periksa_python(dengan) == []
