"""narrate(): jalur LLM, jalur template, dan setiap cara LLM bisa mengecewakan.

Semua lewat FakeLLM — tanpa jaringan, tanpa kunci, supaya suite ini tetap hijau
di mesin juri. [AD-1]
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.llm import FakeLLM, JSONInvalid, LLMError
from core.narrative.generate import PROMPT_VERSION, narrate, template
from core.narrative.validate import unsupported_numbers
from tests.narrative.test_validate import BUKU
from tools.vocab_guard import periksa_teks


@dataclass
class Komposit:
    """Duck-typed: narasi tidak boleh terikat ke tipe milik lajur penilai."""

    pantau_score: int = 74
    band: str = "waspada"
    confidence: float = 0.88


@dataclass
class Langkah:
    probe: str = "broker_concentration"
    finding: str = "confirmed"
    reason: str = "Konsentrasi ekstrem."


LANGKAH = [
    Langkah(),
    Langkah(probe="volume_anomaly", reason="Volume di atas baseline."),
    Langkah(probe="foreign_flow", finding="inconclusive", reason="Arus asing campur."),
]

BERSIH = ("Beberapa indikator menunjukkan pola tidak biasa. Sebanyak 78% net buy "
          "dikuasai tiga broker dan volume berada 4,1σ di atas baseline 90 hari. "
          "Pada periode yang sama asing keluar bersih Rp 184 M.")


def jalankan(jawaban, **kw):
    llm = FakeLLM(responses={PROMPT_VERSION: jawaban}, **kw)
    teks, sumber = narrate(symbol="FIXB", composite=Komposit(), evidence=BUKU,
                           steps=LANGKAH, llm=llm)
    return teks, sumber, llm


def test_narasi_bersih_dipakai_apa_adanya():
    teks, sumber, llm = jalankan(BERSIH)
    assert sumber == "llm"
    assert teks == BERSIH
    assert llm.calls and llm.calls[0][0] == PROMPT_VERSION


def test_angka_karangan_jatuh_ke_template():
    """Inti AD-4: LLM yang mengarang tidak pernah sampai ke pengguna."""
    teks, sumber, _ = jalankan(
        "Volume berada 9,9σ di atas baseline dan asing keluar bersih Rp 900 M."
    )
    assert sumber == "template"
    assert "9,9σ" not in teks and "900 M" not in teks


def test_bahasa_saran_finansial_jatuh_ke_template():
    """Kepatuhan [K5] diperiksa di jalur panas, bukan cuma di CI."""
    # vocab-ok: kalimat terlarang memang bahan ujinya, bukan keluaran ke pengguna
    teks, sumber, _ = jalankan("Volume 4,1σ di atas baseline. Saham ini layak beli sekarang.")
    assert sumber == "template"
    assert not periksa_teks(teks)


@pytest.mark.parametrize("galat", [LLMError("penyedia mati"), JSONInvalid("ngelantur")])
def test_llm_melempar_jatuh_ke_template(galat):
    class LLMRusak:
        def ask_text(self, **_):
            raise galat

    teks, sumber = narrate(symbol="FIXB", composite=Komposit(), evidence=BUKU,
                           steps=LANGKAH, llm=LLMRusak())
    assert sumber == "template"
    assert teks


def test_fakellm_tanpa_jawaban_jatuh_ke_template():
    """FakeLLM melempar JSONInvalid kalau prompt_version tidak dikenal — itu
    persis bentuk kegagalan yang tidak boleh naik ke pemanggil."""
    teks, sumber = narrate(symbol="FIXB", composite=Komposit(), evidence=BUKU,
                           steps=LANGKAH, llm=FakeLLM())
    assert sumber == "template"
    assert teks


def test_keluaran_kosong_jatuh_ke_template():
    _, sumber, _ = jalankan("   ")
    assert sumber == "template"


# ── template itu sendiri ────────────────────────────────────────────────────
def test_template_lolos_validatornya_sendiri():
    """Fallback yang melanggar aturannya sendiri membuat seluruh pagar percuma."""
    teks = template("FIXB", Komposit(), BUKU, LANGKAH)
    assert unsupported_numbers(teks, BUKU) == []


def test_template_lolos_larangan_kosakata():
    teks = template("FIXB", Komposit(), BUKU, LANGKAH)
    assert not periksa_teks(teks)


def test_template_mengutip_bukti_dan_menyebut_ticker():
    teks = template("FIXB", Komposit(), BUKU, LANGKAH)
    assert "FIXB" in teks
    assert "78%" in teks
    assert 3 <= teks.count(". ") + 1 <= 5


@pytest.mark.parametrize("band", ["normal", "perhatian", "waspada", "sangat_waspada"])
def test_template_punya_pembuka_untuk_tiap_band(band):
    teks = template("FIXB", Komposit(band=band), BUKU, LANGKAH)
    assert teks.startswith(("Tidak ada", "Beberapa", "Banyak"))
    assert unsupported_numbers(teks, BUKU) == []
    assert not periksa_teks(teks)


def test_template_tetap_utuh_tanpa_bukti_dan_tanpa_langkah():
    teks = template("FIXB", Komposit(band="normal"), [], [])
    assert teks and unsupported_numbers(teks, []) == []
    assert not periksa_teks(teks)


def test_jumlah_langkah_ditulis_sebagai_kata_bukan_angka():
    """Alasannya ada di docstring validator: kata bukan sitasi, jadi tidak
    menuntut padanan di buku bukti."""
    teks = template("FIXB", Komposit(), BUKU, LANGKAH)
    assert "tiga langkah" in teks
