"""Loop penyelidik: empat perilaku agentik, dan tidak pernah menjatuhkan diri.

Semua memakai FakeLLM dan probe palsu — nol jaringan, nol kunci API. [AD-1]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import Hypothesis, Plan  # noqa: E402
from core.agent import investigator as inv_mod  # noqa: E402
from core.agent.budget import Budget  # noqa: E402
from core.agent.guardrails import Guardrails  # noqa: E402
from core.agent.investigator import investigate  # noqa: E402
from core.llm import FakeLLM  # noqa: E402
from tests.agent.conftest import CtxPalsu, ProbePalsu  # noqa: E402


@pytest.fixture(autouse=True)
def probe_palsu(monkeypatch):
    palsu = {n: ProbePalsu(n) for n in
             ("volume_anomaly", "free_float", "structural", "foreign_flow",
              "broker_concentration", "price_fundamental")}
    monkeypatch.setattr(inv_mod, "PROBES", palsu)
    monkeypatch.setattr(inv_mod, "DESCRIPTIONS", {n: "" for n in palsu})
    return palsu


def rencana(*probes, minta=10):
    return Plan(
        hypotheses=[Hypothesis(id="h1", claim="k", probes=list(probes), priority=1)],
        credit_budget_requested=minta, rationale="r",
    )


def keputusan(**kw):
    dasar = {"finding": "confirmed", "next_action": "continue", "reason": "alasan"}
    return {**dasar, **kw}


def jalankan(plan, jawaban, *, pagu=None):
    llm = FakeLLM(responses={"investigator-v1": jawaban})
    return investigate(symbol="FIXA", plan=plan, ctx=CtxPalsu(),
                       budget=pagu or Budget.for_plan(plan.credit_budget_requested, ceiling=25),
                       llm=llm, guards=Guardrails())


# ── perilaku 1: penghentian dini ────────────────────────────────────────────
def test_penghentian_dini_menyisakan_probe_yang_tidak_dibeli():
    out = jalankan(rencana("volume_anomaly", "free_float", "structural"),
                   [keputusan(next_action="conclude")])
    assert len(out.steps) == 1
    assert out.steps[0].next_action == "conclude"


# ── perilaku 2: eskalasi ────────────────────────────────────────────────────
def test_eskalasi_dikabulkan_mencatat_budget_granted_dan_menyisipkan_probe():
    out = jalankan(rencana("volume_anomaly", minta=4), [
        keputusan(next_action="escalate", new_probe="structural", extra_credits=5),
        keputusan(next_action="conclude"),
    ])
    assert out.steps[0].budget_granted == 5
    assert out.steps[0].new_probe == "structural"
    assert out.steps[1].probe == "structural"


def test_eskalasi_ditolak_agen_tetap_menyimpulkan():
    pagu = Budget.for_plan(25, ceiling=25)  # tidak ada ruang tersisa
    out = jalankan(rencana("volume_anomaly", minta=25), [
        keputusan(next_action="escalate", new_probe="structural", extra_credits=5),
    ], pagu=pagu)
    assert out.steps[0].budget_granted == 0
    assert out.steps[0].new_probe is None
    assert out.steps[-1].next_action == "conclude"


def test_eskalasi_ke_probe_tak_dikenal_diturunkan_bukan_dipercaya():
    out = jalankan(rencana("volume_anomaly"), [
        keputusan(next_action="escalate", new_probe="probe_karangan"),
        keputusan(next_action="conclude"),
    ])
    assert out.steps[0].next_action != "escalate"
    assert out.steps[0].budget_granted == 0


# ── pagar ───────────────────────────────────────────────────────────────────
def test_satu_probe_hanya_sekali_walau_disebut_dua_hipotesis():
    plan = Plan(
        hypotheses=[Hypothesis(id="h1", claim="k", probes=["volume_anomaly"], priority=1),
                    Hypothesis(id="h2", claim="k", probes=["volume_anomaly"], priority=2)],
        credit_budget_requested=10, rationale="r")
    out = jalankan(plan, [keputusan(next_action="continue")] * 4)
    assert [s.probe for s in out.steps] == ["volume_anomaly"]


def test_langkah_terakhir_selalu_conclude_walau_ditutup_paksa():
    out = jalankan(rencana("volume_anomaly", "free_float"),
                   [keputusan(next_action="continue")] * 5)
    assert out.steps[-1].next_action == "conclude"
    assert "ditutup" in out.steps[-1].reason or out.stopped_by


# ── ketahanan ───────────────────────────────────────────────────────────────
def test_llm_gagal_total_investigasi_tetap_menghasilkan_langkah():
    llm = FakeLLM(responses={})  # tiap permintaan melempar JSONInvalid
    out = investigate(symbol="FIXA", plan=rencana("volume_anomaly", "free_float"),
                      ctx=CtxPalsu(), budget=Budget.for_plan(10, ceiling=25),
                      llm=llm, guards=Guardrails())
    assert out.steps and out.fallback_decisions > 0
    assert out.steps[-1].next_action == "conclude"


def test_probe_menyerah_tidak_menjatuhkan_investigasi(monkeypatch, probe_palsu):
    probe_palsu["volume_anomaly"].sub_score = None
    out = jalankan(rencana("volume_anomaly", "free_float"),
                   [keputusan(next_action="continue"), keputusan(next_action="conclude")])
    assert out.results["volume_anomaly"].sub_score is None
    assert len(out.steps) == 2


def test_aritmetika_pagu_utuh_termasuk_eskalasi():
    out = jalankan(rencana("volume_anomaly", minta=4), [
        keputusan(next_action="escalate", new_probe="structural", extra_credits=5),
        keputusan(next_action="conclude"),
    ])
    sisa = 4
    for s in out.steps:
        sisa = sisa - s.credits_spent + s.budget_granted
        assert s.credits_remaining == sisa


# ── eskalasi atas probe yang sudah mengantre tapi belum terbeli ─────────────
# Eval v1 mencatat nol eskalasi dari 16 emiten karena versi pertama menolak setiap
# kandidat yang sudah mengantre. Tes ini mengunci perilaku yang benar.

def test_eskalasi_sah_untuk_probe_antre_yang_pagunya_tidak_cukup():
    plan = rencana("volume_anomaly", "broker_concentration", minta=2)
    out = jalankan(plan, [
        keputusan(next_action="escalate", new_probe="broker_concentration",
                  extra_credits=4),
        keputusan(next_action="conclude"),
    ])
    assert out.steps[0].next_action == "escalate"
    assert out.steps[0].budget_granted > 0
    assert out.steps[1].probe == "broker_concentration"


def test_eskalasi_diturunkan_kalau_probe_toh_sudah_terbeli():
    # Pagu longgar: probe berikutnya akan jalan tanpa tambahan pagu, jadi menyebutnya
    # eskalasi akan membuat transkrip mengaku beradaptasi padahal tidak.
    plan = rencana("volume_anomaly", "free_float", minta=20)
    out = jalankan(plan, [
        keputusan(next_action="escalate", new_probe="free_float"),
        keputusan(next_action="conclude"),
    ])
    assert out.steps[0].next_action == "continue"
    assert out.steps[0].budget_granted == 0


def test_probe_eskalasi_tidak_digandakan_di_antrean():
    plan = rencana("volume_anomaly", "broker_concentration", "free_float", minta=2)
    out = jalankan(plan, [
        keputusan(next_action="escalate", new_probe="broker_concentration",
                  extra_credits=4),
        keputusan(next_action="continue"),
        keputusan(next_action="conclude"),
    ])
    dijalankan = [s.probe for s in out.steps]
    assert len(dijalankan) == len(set(dijalankan))
