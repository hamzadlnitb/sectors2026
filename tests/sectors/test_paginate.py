"""Paginasi. Ini yang menentukan himpunan positif kalibrasi lengkap atau sepotong.

Spike F0: `fetch-suspensions` melaporkan `total_count: 533` tapi satu panggilan
hanya mengirim 20 baris. Pemanggil yang berhenti di halaman pertama akan mengira
sudah menarik 24 bulan — dan Angka 1 dihitung dari 4% data tanpa ada yang sadar.
"""

from __future__ import annotations

from core.sectors.client import CreditAwareClient
from core.sectors.errors import TransportAttemptError
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
        # Server berhak memangkas limit yang diminta — Sectors memang begitu.
        limit = min(int(params.get("limit", self.per_halaman)), self.per_halaman)
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
    """Paginasi bukan jalan pintas melewati pagu kredit.

    Pagu yang tertembus MENGHENTIKAN penelusuran, tapi tidak membuang halaman
    yang sudah dibayar. Versi pertama melempar exception dan menghanguskan
    seluruh hasil — 50 kredit terbakar untuk nol baris, sungguhan, 8 Sep."""
    t = HalamanTransport(total=1_000, per_halaman=100)
    client = buat(tmp_path, t, cap=3)

    rows, credits = client.paginate("fetch-suspensions", {}, max_pages=50)

    assert client.ledger.spent("dev") == 3, "pagu tetap ditegakkan"
    assert credits == 3
    assert len(rows) == 300, "tiga halaman yang sudah dibayar tetap terpakai"


def test_halaman_gagal_tidak_menghanguskan_yang_sudah_dibayar(tmp_path):
    """Kejadian nyata: fetch-filings kena 429 di halaman ke-51 dan seluruh 50
    halaman sebelumnya hilang bersama exception-nya."""
    class Rewel(HalamanTransport):
        def fetch(self, endpoint, params):
            if int(params.get("offset", 0)) >= 200:
                raise TransportAttemptError("HTTP 429", retryable=False, status=429)
            return super().fetch(endpoint, params)

    client = buat(tmp_path, Rewel(total=1_000, per_halaman=100))
    rows, credits = client.paginate("fetch-suspensions", {}, max_pages=50)

    assert len(rows) == 200 and credits == 2
    assert client.ledger.spent("dev") == 2


def test_pagu_kredit_menghentikan_paginasi_yang_kepanjangan(tmp_path):
    """Pagar halaman tidak tahu harga. 50 halaman = 50 kredit untuk rencana yang
    menganggarkan 3, dan tidak ada peringatan sampai ledger dibaca."""
    t = HalamanTransport(total=10_000, per_halaman=100)
    rows, credits = buat(tmp_path, t).paginate(
        "fetch-suspensions", {}, max_pages=50, max_credits=4)
    assert credits == 4 and len(rows) == 400


def test_limit_yang_dipangkas_server_diikuti(tmp_path):
    """Sectors memangkas limit 100 jadi ~20. Memakai angka kita sendiri membuat
    perkiraan halaman meleset berlipat, dan itu yang bikin anggaran jebol."""
    t = HalamanTransport(total=60, per_halaman=20)
    rows, credits = buat(tmp_path, t).paginate("fetch-suspensions", {}, page_size=100)
    assert len(rows) == 60
    assert credits == 3, "60 baris / 20 per halaman = 3 panggilan"


def test_halaman_kedua_kena_cache_saat_diulang(tmp_path):
    """Backfill yang diulang setelah gagal di tengah tidak membayar dua kali. [AD-3]"""
    t = HalamanTransport(total=250, per_halaman=100)
    client = buat(tmp_path, t)
    _, pertama = client.paginate("fetch-suspensions", {"start": "2024-09-08"})
    _, kedua = client.paginate("fetch-suspensions", {"start": "2024-09-08"})

    assert pertama == 3 and kedua == 0
    assert client.ledger.spent("dev") == 3
