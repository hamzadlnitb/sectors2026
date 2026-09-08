"""Redaksi kunci API. Repo publik ≥90 hari — satu kebocoran di log CI sudah cukup."""

from __future__ import annotations

import logging

from core.sectors import redact


def test_kunci_terdaftar_disensor():
    redact.register("sk-rahasia-panjang-sekali-123")
    assert "sk-rahasia" not in redact.scrub("gagal auth: sk-rahasia-panjang-sekali-123")
    assert redact.MASK in redact.scrub("token=sk-rahasia-panjang-sekali-123")


def test_pola_header_disensor_walau_kunci_belum_terdaftar():
    """Kunci milik orang lain yang tidak sengaja tertempel tetap tertutup."""
    assert redact.MASK in redact.scrub("Authorization: Bearer abcdef1234567890")
    assert redact.MASK in redact.scrub('{"api_key": "xyz9876543210abc"}')


def test_potongan_pendek_tidak_didaftarkan():
    """Rahasia sependek 'abc' akan mencocoki teks biasa dan mengubah log jadi bubur."""
    redact.register("abc")
    assert redact.scrub("abcdefg") == "abcdefg"


def test_filter_tidak_merusak_penanda_format(caplog):
    """Filter keamanan yang membuat log error justru menyembunyikan kejadiannya."""
    log = redact.get_logger("tes.redaksi")
    with caplog.at_level(logging.INFO, logger="tes.redaksi"):
        log.info("percobaan %d/%d gagal (%s), tunggu %.1fs", 1, 4, "HTTP 503", 0.5)
    assert "percobaan 1/4 gagal (HTTP 503), tunggu 0.5s" in caplog.text


def test_filter_menyensor_argumen_string(caplog):
    redact.register("sk-bocor-abcdefghij")
    log = redact.get_logger("tes.redaksi2")
    with caplog.at_level(logging.WARNING, logger="tes.redaksi2"):
        log.warning("gagal: %s", "auth ditolak untuk sk-bocor-abcdefghij")
    assert "sk-bocor-abcdefghij" not in caplog.text
    assert redact.MASK in caplog.text
