"""Investigasi utuh tanpa jaringan → transkrip yang lolos kontrak.

Ini tes yang paling berharga di lajur agen: ia menjalankan ketiga tahap sungguhan
dan memvalidasi hasilnya dengan validator yang sama yang dipakai CI. Kalau tes
ini hijau, `make demo` di mesin juri juga hijau. [AD-1][AD-2]
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.check import check  # noqa: E402
from core.agent import investigator as inv_mod  # noqa: E402
from core.agent.adjudicator import adjudicate  # noqa: E402
from core.agent.budget import Budget  # noqa: E402
from core.agent.investigator import investigate  # noqa: E402
from core.agent.transcript import save  # noqa: E402
from core.llm import FakeLLM  # noqa: E402
from tests.agent.conftest import CtxPalsu, ProbePalsu  # noqa: E402


@pytest.fixture
def probe_palsu(monkeypatch):
    palsu = {n: ProbePalsu(n, sub_score=70.0) for n in
             ("volume_anomaly", "free_float", "structural", "foreign_flow",
              "broker_concentration", "price_fundamental")}
    monkeypatch.setattr(inv_mod, "PROBES", palsu)
    monkeypatch.setattr(inv_mod, "DESCRIPTIONS", {n: "" for n in palsu})
    import core.agent.adjudicator as adj
    monkeypatch.setattr(adj, "PROBES", palsu)
    return palsu


def test_transkrip_hasil_agen_lolos_validator_kontrak(probe_palsu, rencana, tmp_path):
    llm = FakeLLM(responses={"investigator-v1": [
        {"finding": "confirmed", "next_action": "continue", "reason": "lanjut"},
        {"finding": "confirmed", "next_action": "conclude", "reason": "cukup"},
    ]})
    inv = investigate(symbol="FIXA", plan=rencana, ctx=CtxPalsu(),
                      budget=Budget.for_plan(10, ceiling=25), llm=llm)

    t = adjudicate(symbol="FIXA", as_of=date(2026, 9, 9), plan=rencana,
                   inv=inv, llm=llm)
    path = save(t, root=tmp_path)

    assert check(path) == [], check(path)


def test_investigasi_tanpa_satu_pun_probe_berhasil_tetap_sah(probe_palsu, rencana, tmp_path):
    for p in probe_palsu.values():
        p.sub_score = None
    llm = FakeLLM(responses={"investigator-v1": [
        {"finding": "inconclusive", "next_action": "conclude", "reason": "menyerah"},
    ]})
    inv = investigate(symbol="FIXA", plan=rencana, ctx=CtxPalsu(),
                      budget=Budget.for_plan(10, ceiling=25), llm=llm)
    t = adjudicate(symbol="FIXA", as_of=date(2026, 9, 9), plan=rencana, inv=inv, llm=llm)

    assert t.confidence == 0.0
    assert check(save(t, root=tmp_path)) == []


def test_kredit_tidak_pernah_melebihi_baseline_menyeluruh(probe_palsu, rencana, tmp_path):
    llm = FakeLLM(responses={"investigator-v1": [
        {"finding": "confirmed", "next_action": "continue", "reason": "r"},
    ] * 8})
    inv = investigate(symbol="FIXA", plan=rencana, ctx=CtxPalsu(),
                      budget=Budget.for_plan(25, ceiling=25), llm=llm)
    t = adjudicate(symbol="FIXA", as_of=date(2026, 9, 9), plan=rencana, inv=inv, llm=llm)
    assert t.credits_total <= t.baseline_credits
