"""Buku bukti — satu-satunya sumber angka yang boleh muncul di narasi.

Validator sitasi mencocokkan tiap token angka dalam narasi ke daftar ini. Kalau
sebuah angka tidak lahir dari probe, ia tidak ada di sini, dan narasi yang
menyebutnya ditolak. Itulah yang membuat halusinasi angka mustahil lolos —
bukan prompt yang memohon supaya jujur. [AD-4]
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import EvidenceEntry, ProbeResult  # noqa: E402


def evidence_book(results: Mapping[str, ProbeResult]) -> list[EvidenceEntry]:
    """Gabungkan bukti dari semua probe yang berhasil, urut stabil.

    Probe yang menyerah (`sub_score` None) tidak menyumbang bukti: kontrak sudah
    mengosongkan `evidence` untuk kasus itu, dan menampilkan bukti separuh dari
    probe yang gagal akan menyesatkan pembaca transkrip.

    Urutan mengikuti nama probe lalu id bukti — bukan urutan dict — supaya dua
    investigasi dengan probe sama menghasilkan buku bukti identik. Transkrip
    yang bisa diputar ulang harus stabil sampai ke urutan barisnya. [AD-1]
    """
    book: list[EvidenceEntry] = []
    for probe in sorted(results):
        hasil = results[probe]
        if hasil.sub_score is None:
            continue
        book.extend(sorted(hasil.evidence, key=lambda e: e.id))
    return book


def index(evidence: Iterable[EvidenceEntry]) -> dict[str, EvidenceEntry]:
    """Buku bukti sebagai peta id → entri.

    Id yang sama muncul dua kali berarti dua probe mengklaim angka yang sama.
    Yang pertama menang dan itu disengaja: id bukti adalah nama kanonik sebuah
    fakta, jadi menimpanya diam-diam akan membuat narasi menunjuk ke sumber yang
    berbeda dari yang dipakai skor.
    """
    peta: dict[str, EvidenceEntry] = {}
    for entry in evidence:
        peta.setdefault(entry.id, entry)
    return peta
