"""Skor komposit: aturan yang divalidasi contracts/check.py dijaga di sini."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import ProbeResult, band_for_score  # noqa: E402
from core.scoring.composite import WEIGHTS, score  # noqa: E402
from core.scoring.facts import evidence_book, index  # noqa: E402
from tests.agent.conftest import hasil  # noqa: E402


def test_bobot_berjumlah_satu():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_enam_komponen_selalu_dilaporkan():
    out = score({})
    assert len(out.components) == 6
    assert all(not c.investigated for c in out.components)


def test_keyakinan_sama_dengan_bobot_terselidiki():
    out = score({"volume_anomaly": hasil("volume_anomaly", 80.0)})
    assert abs(out.confidence - WEIGHTS["VAS"]) < 0.011


def test_probe_menyerah_dihitung_tidak_diselidiki_bukan_nol():
    menyerah = ProbeResult(probe="volume_anomaly", sub_score=None,
                           unavailable_reason="data kurang", credits_spent=3)
    out = score({"volume_anomaly": menyerah})
    assert out.confidence == 0.0
    assert out.components[1].investigated is False


def test_skor_hanya_atas_komponen_terselidiki():
    # Satu probe bernilai 90 harus menghasilkan 90, bukan 90 dibagi enam.
    out = score({"volume_anomaly": hasil("volume_anomaly", 90.0)})
    assert out.pantau_score == 90


def test_band_selalu_dari_band_for_score():
    for nilai in (0, 29, 30, 59, 60, 79, 80, 100):
        out = score({"volume_anomaly": hasil("volume_anomaly", float(nilai))})
        assert out.band == band_for_score(out.pantau_score)


def test_bobot_yang_tidak_berjumlah_satu_dinormalisasi():
    out = score({"volume_anomaly": hasil("volume_anomaly", 50.0)},
                weights={"BCI": 2, "VAS": 2, "PFD": 2, "FFS": 2, "FRD": 2, "SSS": 2})
    assert abs(out.confidence - 1 / 6) < 0.01


def test_buku_bukti_stabil_urutannya():
    a = {"volume_anomaly": hasil("volume_anomaly"), "free_float": hasil("free_float")}
    b = {"free_float": a["free_float"], "volume_anomaly": a["volume_anomaly"]}
    assert [e.id for e in evidence_book(a)] == [e.id for e in evidence_book(b)]


def test_buku_bukti_membuang_probe_yang_menyerah():
    menyerah = ProbeResult(probe="free_float", sub_score=None,
                           unavailable_reason="kosong", credits_spent=1)
    book = evidence_book({"volume_anomaly": hasil("volume_anomaly"), "free_float": menyerah})
    assert all(e.probe == "volume_anomaly" for e in book)


def test_index_mempertahankan_entri_pertama():
    e = hasil("volume_anomaly").evidence[0]
    assert index([e, e.model_copy(update={"display": "beda"})])[e.id].display == e.display
