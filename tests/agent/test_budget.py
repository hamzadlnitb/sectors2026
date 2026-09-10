"""Pagu adalah alasan keberadaan agen, jadi aritmetikanya harus utuh."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.agent.budget import ESCALATION_LIMIT, Budget  # noqa: E402


def test_permintaan_di_atas_pagar_dipotong_bukan_ditolak():
    b = Budget.for_plan(999, ceiling=25)
    assert b.pool == 25 and b.ceiling == 25


def test_eskalasi_tidak_pernah_melewati_pagar_keras():
    b = Budget.for_plan(20, ceiling=25)
    b.commit(b.preview(50))
    assert b.pool == 25


def test_eskalasi_dibatasi_jumlahnya():
    b = Budget.for_plan(1, ceiling=25)
    for _ in range(ESCALATION_LIMIT):
        assert b.commit(b.preview(2)) > 0
    grant = b.preview(2)
    assert not grant.accepted and "eskalasi" in grant.reason


def test_eskalasi_ditolak_saat_pagu_sudah_menyentuh_pagar():
    b = Budget.for_plan(25, ceiling=25)
    grant = b.preview(5)
    assert not grant.accepted and "pagar keras" in grant.reason


def test_preview_tidak_mengubah_apa_pun():
    b = Budget.for_plan(10, ceiling=25)
    sebelum = (b.pool, b.spent, b.escalations)
    b.preview(5)
    assert (b.pool, b.spent, b.escalations) == sebelum


def test_belanja_berlebih_dipotong_agar_sisa_tidak_negatif():
    b = Budget.for_plan(4, ceiling=25)
    assert b.charge(10) == 4
    assert b.remaining == 0


def test_refund_mengembalikan_pagu_yang_tidak_jadi_dipakai():
    b = Budget.for_plan(5, ceiling=25)
    b.commit(b.preview(6))
    pool = b.pool
    assert b.refund(6) == 6
    assert b.pool == pool - 6
