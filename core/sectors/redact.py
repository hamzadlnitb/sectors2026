"""Redaksi kunci API di seluruh log dan pesan error. [AD-3]

Repo ini publik dan wajib tetap publik ≥90 hari. Satu kunci yang bocor lewat
log CI — yang tersimpan di GitHub Actions dan bisa dibaca siapa pun — cukup
untuk mencabut kredit tim.

Karena itu redaksi tidak diserahkan ke kedisiplinan orang yang menulis
f-string. Kunci didaftarkan sekali, lalu:

* filter logging memotongnya dari tiap record yang lewat, apa pun modulnya;
* scrub() dipakai di jalur error, tempat payload dan URL ikut tercetak.

Yang tidak dijamin modul ini: print() langsung ke stdout. Karena itu jalur
jaringan tidak boleh memakai print — pakai get_logger().
"""

from __future__ import annotations

import logging
import os
import re

MASK = "***REDACTED***"
_MIN_LEN = 8  # potongan pendek terlalu berisiko cocok dengan teks biasa

_secrets: set[str] = set()
_pattern: re.Pattern[str] | None = None

# Bentuk yang sering muncul walau kuncinya sendiri belum terdaftar
# (mis. kunci milik orang lain di log yang kita tempel ke issue).
# Tiap pola punya PERSIS satu grup: awalan yang tetap terlihat. Sisanya ditutup.
_HEADER_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[\w.\-]{8,}"),
    re.compile(r"(?i)((?:api[_-]?key|x-api-key|token)\s*[\"']?\s*[:=]\s*[\"']?)[\w.\-]{8,}"),
]


def register(secret: str | None) -> None:
    """Daftarkan satu rahasia. Aman dipanggil berkali-kali."""
    global _pattern
    if not secret or len(secret) < _MIN_LEN:
        return
    _secrets.add(secret)
    _pattern = re.compile("|".join(re.escape(s) for s in sorted(_secrets, key=len, reverse=True)))


def register_from_env(*names: str) -> None:
    for name in names or ("SECTORS_API_KEY",):
        register(os.environ.get(name))


def scrub(text: object) -> str:
    """Buang setiap rahasia terdaftar, lalu tutup pola header yang mencurigakan."""
    out = text if isinstance(text, str) else str(text)
    if _pattern is not None:
        out = _pattern.sub(MASK, out)
    for pat in _HEADER_PATTERNS:
        out = pat.sub(lambda m: m.group(1) + MASK, out)
    return out


class RedactingFilter(logging.Filter):
    """Memotong rahasia dari pesan DAN dari argumen format.

    Hanya argumen bertipe str yang disentuh. Mengubah angka jadi string akan
    merusak penanda format seperti %d dan %.1f — filter keamanan yang bikin log
    error justru menyembunyikan kejadian yang mau dicatat.
    """

    @staticmethod
    def _arg(value: object) -> object:
        return scrub(value) if isinstance(value, str) else value

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._arg(v) for k, v in record.args.items()}
            else:
                record.args = tuple(self._arg(a) for a in record.args)
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            exc.args = tuple(scrub(a) for a in exc.args)
        return True


_FILTER = RedactingFilter()


def get_logger(name: str) -> logging.Logger:
    """Logger yang dijamin sudah membawa filter redaksi."""
    logger = logging.getLogger(name)
    if not any(isinstance(f, RedactingFilter) for f in logger.filters):
        logger.addFilter(_FILTER)
    return logger


def install(secret: str | None = None) -> None:
    """Pasang filter di root logger. Dipanggil sekali saat klien dibuat."""
    register(secret)
    register_from_env()
    root = logging.getLogger()
    if not any(isinstance(f, RedactingFilter) for f in root.filters):
        root.addFilter(_FILTER)
    for handler in root.handlers:
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(_FILTER)
