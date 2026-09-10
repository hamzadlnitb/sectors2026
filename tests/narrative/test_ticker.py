"""Narasi tidak boleh menyebut emiten selain yang diselidiki.

Kasus di berkas ini bukan hipotesis: ketiganya diambil dari keluaran MiniMax
sungguhan pada uji end-to-end pertama, yang lolos validator angka tetapi
menyebut "JAJA" untuk investigasi "JAWA". [contracts/CHANGES.md C3]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.narrative.validate import unsupported_tickers  # noqa: E402

NARASI_ASLI = (
    "Investigasi pada saham JAJA menemukan bahwa free float hanya 8%, kondisi "
    "yang membuat pergerakan harga rentan dipengaruhi modal terbatas."
)


def test_emiten_karangan_tertangkap():
    assert unsupported_tickers(NARASI_ASLI, "JAWA") == ["JAJA"]


def test_emiten_benar_lolos():
    assert unsupported_tickers(NARASI_ASLI.replace("JAJA", "JAWA"), "JAWA") == []


@pytest.mark.parametrize("istilah", ["RUPS", "IUPK"])
def test_istilah_pasar_modal_bukan_halusinasi(istilah):
    assert unsupported_tickers(f"Emiten JAWA menggelar {istilah} tahun ini.", "JAWA") == []


def test_beberapa_emiten_asing_dilaporkan_sekali_masing_masing():
    teks = "JAWA dibandingkan BBCA, lalu BBCA lagi, dan TLKM."
    assert unsupported_tickers(teks, "JAWA") == ["BBCA", "TLKM"]


def test_simbol_dicocokkan_tanpa_peduli_huruf_besar_kecil():
    assert unsupported_tickers("Saham JAWA stabil.", "jawa") == []
