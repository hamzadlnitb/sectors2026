"""Kesalahan yang bisa keluar dari gateway Sectors.

Satu hierarki supaya pemanggil bisa membedakan "kredit habis" (berhenti) dari
"respons rusak" (laporkan) dari "jaringan ngambek" (sudah di-retry, menyerah).
Tidak ada yang boleh muncul sebagai KeyError atau IndexError di lapisan atas.
"""

from __future__ import annotations


class SectorsError(Exception):
    """Akar semua kesalahan gateway."""


class BudgetExceeded(SectorsError):
    """Panggilan ditolak karena menembus pagu fase. [AD-5]

    Ini raise, bukan warning. Pagu yang cuma diperingatkan bukan pagu.
    """

    def __init__(self, phase: str, requested: int, spent: int, cap: int) -> None:
        self.phase, self.requested, self.spent, self.cap = phase, requested, spent, cap
        super().__init__(
            f"pagu fase '{phase}' tertembus: sudah {spent}/{cap} kredit, "
            f"panggilan ini minta {requested} lagi"
        )


class TransportAttemptError(SectorsError):
    """Satu percobaan gagal. Dilempar transport, ditangkap loop retry di klien.

    `retryable` memisahkan yang layak dicoba lagi (429, 5xx, timeout) dari yang
    tidak (401, 404) — mengulang panggilan yang salah kunci cuma membakar waktu.
    `charged` menandai percobaan yang kemungkinan besar tetap memotong kredit.
    """

    def __init__(self, detail: str, *, retryable: bool, status: int | None = None,
                 charged: bool = False) -> None:
        self.detail, self.retryable, self.status, self.charged = detail, retryable, status, charged
        super().__init__(detail)


class TransportError(SectorsError):
    """Jaringan gagal setelah seluruh retry habis."""

    def __init__(self, endpoint: str, attempts: int, last: str) -> None:
        self.endpoint, self.attempts = endpoint, attempts
        super().__init__(f"'{endpoint}' gagal setelah {attempts} percobaan: {last}")


class SchemaError(SectorsError):
    """Respons sampai, tapi bentuknya bukan yang kita harapkan.

    Membawa cuplikan payload yang SUDAH diredaksi supaya bisa didiagnosis tanpa
    membocorkan apa pun ke log. [AD-3]
    """

    def __init__(self, endpoint: str, detail: str, preview: str) -> None:
        self.endpoint, self.preview = endpoint, preview
        super().__init__(f"respons '{endpoint}' tidak sesuai skema: {detail}\n  cuplikan: {preview}")


class UnknownEndpoint(SectorsError):
    """Endpoint tidak ada di tabel perutean.

    Sengaja keras: kalau nama endpoint boleh bebas, biaya kreditnya tidak bisa
    diketahui sebelum dipanggil, dan penganggaran jadi tebakan. [AD-7]
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"endpoint '{name}' tidak terdaftar di core/sectors/routing.py")


class TransportUnavailable(SectorsError):
    """Transport yang diminta tidak bisa dipakai (mis. MCP mati, tidak ada kunci)."""
