"""Paginasi. Ini yang menentukan himpunan positif kalibrasi lengkap atau sepotong.

Spike F0: `fetch-suspensions` melaporkan `total_count: 533` tapi satu panggilan
hanya mengirim 20 baris. Pemanggil yang berhenti di halaman pertama akan mengira
sudah menarik 24 bulan — dan Angka 1 dihitung dari 4% data tanpa ada yang sadar.
"""

from __future__ import annotations

import pytest

from core.sectors.client import CreditAwareClient
from core.sectors.ledger import CreditLedger


def _ticker(i: int) -> str:
    """Ticker uji 4 huruf. Kontrak mematok ^[A-Z]{4}$ — angka ditolak validator,
    dan fixture yang melanggarnya menguji validator, bukan paginasi."""
    huruf = ""
    for _ in range(4):
        huruf = chr(ord("A") + i % 26) + huruf
        i //= 26
    return huruf


class HalamanTransport:
    """Meniru bentuk paginasi Sectors: {results, pagination}."""

    name = "rest"

    def __init__(self, total: int, per_halaman: int = 100, rusak: str | None = None):
        self.total, self.per_halaman, self.rusak = total, per_halaman, rusak
        self.offsets: list[int] = []

    def fetch(self, endpoint, params):
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", self.per_halaman))
        self.offsets.append(offset)
        baris = [
            {"symbol": _ticker(i),
             "suspension_date": "2026-09-04", "reason": "Pergerakan harga di luar kebiasaan"}
            for i in range(offset, min(offset + limit, self.total))
        ]
        berikut = offset + limit
        next_offset = berikut if berikut < self.total else None
        if self.rusak == "mandek":
            next_offset = offset  # tidak pernah maju
        if self.rusak == "selamanya":
            next_offset = berikut  # has_next selamanya True
        return {
            "results": baris,
            "pagination": {
                "total_count": self.total, "showing": len(baris), "limit": limit,
                "offset": offset,
                "has_next": next_offset is not None or self.rusak == "selamanya",
                "next_offset": next_offset,
            },
        }

    def close(self):
        pass


def buat(tmp_path, transport, cap=500):
    return CreditAwareClient(
        api_key="k" * 20, ledger=CreditLedger(tmp_path / "l.jsonl", caps={"dev": cap}),
        cache_dir=tmp_path / "c", rest=transport, sleep=lambda _: None,
    )


def test_seluruh_halaman_ditelusuri(tmp_path):
    t = HalamanTransport(total=533, per_halaman=100)
    rows, credits = buat(tmp_path, t).paginate("fetch-suspensions", {"start": "2024-09-08"})

    assert len(rows) == 533, "berhenti sebelum habis = himpunan positif sepotong"
    assert t.offsets == [0, 100, 200, 300, 400, 500]
    assert credits == 6, "satu halaman satu kredit"


def test_satu_halaman_cukup_tidak_memanggil_lagi(tmp_path):
    t = HalamanTransport(total=12, per_halaman=100)
    rows, credits = buat(tmp_path, t).paginate("fetch-suspensions", {})
    assert len(rows) == 12 and credits == 1
    assert t.offsets == [0]


def test_pagar_halaman_menghentikan_paginasi_rusak(tmp_path):
    """has_next selamanya True akan menghabiskan seluruh pagu fase dalam detik."""
    t = HalamanTransport(total=10_000, per_halaman=10, rusak="selamanya")
    rows, credits = buat(tmp_path, t).paginate("fetch-suspensions", {}, page_size=10,
                                               max_pages=5)
    assert credits == 5 and len(t.offsets) == 5
    assert len(rows) == 50


def test_offset_yang_tidak_maju_dihentikan(tmp_path):
    """Server yang mengembalikan next_offset sama = putaran tak berujung."""
    t = HalamanTransport(total=1_000, per_halaman=10, rusak="mandek")
    _, credits = buat(tmp_path, t).paginate("fetch-suspensions", {}, page_size=10,
                                            max_pages=50)
    assert credits == 1, "harus berhenti setelah sadar offset tidak bergerak"


def test_pagu_tetap_ditegakkan_di_tengah_penelusuran(tmp_path):
    """Paginasi bukan jalan pintas melewati pagu kredit."""
    from core.sectors.errors import BudgetExceeded

    t = HalamanTransport(total=1_000, per_halaman=100)
    client = buat(tmp_path, t, cap=3)
    with pytest.raises(BudgetExceeded):
        client.paginate("fetch-suspensions", {}, max_pages=50)
    assert client.ledger.spent("dev") == 3


def test_halaman_kedua_kena_cache_saat_diulang(tmp_path):
    """Backfill yang diulang setelah gagal di tengah tidak membayar dua kali. [AD-3]"""
    t = HalamanTransport(total=250, per_halaman=100)
    client = buat(tmp_path, t)
    _, pertama = client.paginate("fetch-suspensions", {"start": "2024-09-08"})
    _, kedua = client.paginate("fetch-suspensions", {"start": "2024-09-08"})

    assert pertama == 3 and kedua == 0
    assert client.ledger.spent("dev") == 3
