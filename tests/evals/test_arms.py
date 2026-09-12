"""Lengan eval: pembanding harus benar-benar membanding, bukan meniru agen."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals import arms  # noqa: E402
from tests.agent.conftest import ProbePalsu  # noqa: E402


@dataclass
class Ctx:
    as_of: date = date(2026, 9, 11)
    budget_remaining: int = 999
    spent: int = 0
    warehouse: object = None
    client: object = None
    phase: str = "eval"
    fetched: list = field(default_factory=list)


@pytest.fixture(autouse=True)
def probe_palsu(monkeypatch):
    biaya = {"broker_concentration": 6, "volume_anomaly": 1, "price_fundamental": 5,
             "free_float": 1, "foreign_flow": 2, "structural": 3}
    palsu = {n: ProbePalsu(n, sub_score=70.0, biaya=b) for n, b in biaya.items()}
    monkeypatch.setattr(arms, "PROBES", palsu)
    monkeypatch.setattr(arms, "URUTAN_TETAP", tuple(palsu))
    import core.agent.guardrails as g
    monkeypatch.setattr(g, "PROBES", palsu, raising=False)
    return palsu


def test_menyeluruh_menjalankan_keenam_probe():
    out = arms.menyeluruh("FIXA", Ctx())
    assert len(out.probes_run) == 6
    assert out.credits == arms.baseline_credits("FIXA") == 18


def test_urutan_tetap_berhenti_saat_pagu_habis():
    out = arms.urutan_tetap("FIXA", Ctx(), pagu=8)
    assert out.credits <= 8
    assert len(out.probes_run) < 6


def test_acak_berbibit_tetap_sehingga_bisa_diulang():
    a = arms.acak("FIXA", Ctx(), pagu=8)
    b = arms.acak("FIXA", Ctx(), pagu=8)
    assert a.probes_run == b.probes_run


def test_acak_berbeda_antar_emiten():
    # Bibit tunggal untuk semua emiten akan membuat lengan ini bukan benar-benar acak.
    pilihan = {s: tuple(arms.acak(s, Ctx(), pagu=9).probes_run)
               for s in ("FIXA", "FIXB", "FIXC", "FIXD", "FIXE")}
    assert len(set(pilihan.values())) > 1


def test_pembanding_tidak_pernah_melampaui_pagu():
    for pagu in (1, 3, 7, 12):
        assert arms.urutan_tetap("FIXA", Ctx(), pagu).credits <= pagu
        assert arms.acak("FIXA", Ctx(), pagu).credits <= pagu


def test_kredit_terhitung_memakai_cost_estimate_bukan_laporan_probe(monkeypatch, probe_palsu):
    """Biaya lengan diambil dari cost_estimate, bukan dari credits_spent probe.

    Bedanya menentukan: credits_spent bergantung pada apa yang kebetulan sudah ada
    di warehouse saat eval berjalan, sedangkan cost_estimate adalah angka yang sama
    yang dilihat perencana saat memilih. Kalau metriknya ikut cache, lengan-lengan
    ini dibandingkan dengan penggaris yang berbeda-beda.
    """
    out = arms.menyeluruh("FIXA", Ctx())
    dilaporkan = sum(r.credits_spent for r in out.results.values())

    # Probe berpura-pura tidak membelanjakan apa pun; biaya lengan tidak berubah.
    for p in probe_palsu.values():
        p.biaya_lapor = 0
    monkeypatch.setattr(arms.PROBES["volume_anomaly"], "biaya", 1)
    assert out.credits == arms.baseline_credits("FIXA") == 18
    assert out.credits != dilaporkan or dilaporkan == 18


def test_probe_menyerah_tetap_dihitung_biayanya(probe_palsu):
    # Probe yang menyerah tetap membakar kredit di dunia nyata; lengan yang
    # mengabaikannya akan terlihat lebih hemat daripada yang sebenarnya.
    probe_palsu["volume_anomaly"].sub_score = None
    out = arms.menyeluruh("FIXA", Ctx())
    assert "volume_anomaly" in out.probes_run
    assert out.credits == 18
