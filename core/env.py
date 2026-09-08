"""Muat .env sekali, di satu tempat.

.env.example menyuruh orang menyalin berkasnya lalu mengisi kunci. Kalau tidak
ada yang benar-benar memuatnya, perintah pertama yang dijalankan orang itu akan
gagal dengan "SECTORS_API_KEY tidak diset" padahal kuncinya sudah ada di berkas
— dan yang dicurigai duluan pasti kuncinya, bukan kodenya.

Variabel lingkungan yang SUDAH ada tidak ditimpa. Itu penting untuk GitHub
Actions: di sana kunci datang dari Secrets, tidak ada .env sama sekali, dan
.env yang tidak sengaja terbawa tidak boleh menang atas Secrets.

Plumbing bersama lajur data. Lajur lain bebas memakainya.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

_loaded = False


def load_env(path: Path | None = None, force: bool = False) -> bool:
    """Muat .env kalau ada. True kalau berkasnya terbaca.

    Idempoten: aman dipanggil dari tiap entrypoint tanpa perlu tahu apakah
    entrypoint lain sudah memanggilnya.
    """
    global _loaded
    if _loaded and not force:
        return True

    target = path or ENV_PATH
    if not target.exists():
        _loaded = True
        return False

    try:
        from dotenv import load_dotenv
    except ImportError:
        # python-dotenv opsional: tanpanya, .env diurai seadanya. Lebih baik
        # daripada memaksa orang memasang paket untuk membaca lima baris.
        _parse_simple(target)
    else:
        load_dotenv(target, override=False)

    _loaded = True
    return True


def _parse_simple(path: Path) -> None:
    """Pengurai cadangan: KEY=value, satu per baris."""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
