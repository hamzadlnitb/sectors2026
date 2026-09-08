"""Keluaran konsol yang tidak mati di Windows.

Konsol Windows bawaan memakai cp1252, dan seluruh keluaran kita berbahasa
Indonesia dengan simbol seperti σ, ×, dan → di dalamnya. Tanpa ini,
`python -m core.ingest.tier1_market` **crash dengan UnicodeEncodeError** di
mesin juri yang memakai Windows — bukan tampil jelek, tapi gagal total dengan
traceback, setelah kredit terlanjur dibelanjakan.

errors="backslashreplace" dipilih daripada "replace": pada konsol yang benar-benar
tidak bisa menampilkan karakternya, yang muncul \\u03c3 (masih bisa dibaca) alih-alih
tanda tanya yang menghilangkan informasi.

Plumbing bersama lajur data. Lajur lain bebas memakainya.

    from core.console import setup_console
    setup_console()
"""

from __future__ import annotations

import contextlib
import sys


def setup_console() -> None:
    """Panggil sekali di awal tiap entrypoint CLI. Aman dipanggil berulang."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue  # stdout diganti pytest / pipa; biarkan apa adanya
        # Stream yang tidak mendukung reconfigure: biarkan apa adanya, keluaran
        # tetap jalan seperti sebelumnya.
        with contextlib.suppress(ValueError, OSError):
            reconfigure(encoding="utf-8", errors="backslashreplace")
