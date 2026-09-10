"""Perkakas bersama tes agen. Nol jaringan, nol kunci API."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import EvidenceEntry, Hypothesis, Plan, ProbeResult  # noqa: E402

WIB = timezone(timedelta(hours=7))


def bukti(id_: str, probe: str, credits: int = 0) -> EvidenceEntry:
    return EvidenceEntry(
        id=id_, label=f"label {id_}", value=1.0, display="1,0", probe=probe,
        source_endpoint="fetch-daily-transaction", source_params={"symbol": "FIXA"},
        source_transport="rest", as_of=datetime(2026, 9, 9, 16, 0, tzinfo=WIB),
        credits_spent=credits,
    )


def hasil(probe: str, sub_score: float | None = 50.0, credits: int = 2) -> ProbeResult:
    if sub_score is None:
        return ProbeResult(probe=probe, sub_score=None,
                           unavailable_reason="data tidak cukup", credits_spent=credits)
    return ProbeResult(probe=probe, sub_score=sub_score,
                       evidence=[bukti(f"{probe}.x", probe, credits)], credits_spent=credits)


@dataclass
class ProbePalsu:
    """Probe yang tidak menyentuh jaringan maupun warehouse."""

    name: str
    sub_score: float | None = 50.0
    biaya: int = 2
    dipanggil: int = 0

    def cost_estimate(self, symbol: str) -> int:
        return self.biaya

    def run(self, symbol: str, ctx) -> ProbeResult:
        self.dipanggil += 1
        ctx.spent += self.biaya
        return hasil(self.name, self.sub_score, self.biaya)


@dataclass
class CtxPalsu:
    """Context minimal — penyelidik hanya memakai budget_remaining dan spent."""

    as_of: date = date(2026, 9, 9)
    budget_remaining: int = 25
    spent: int = 0
    warehouse: object = None
    client: object = None
    phase: str = "test"
    fetched: list = field(default_factory=list)


@pytest.fixture
def rencana() -> Plan:
    return Plan(
        hypotheses=[
            Hypothesis(id="h1", claim="klaim satu",
                       probes=["volume_anomaly", "free_float"], priority=1),
        ],
        credit_budget_requested=10,
        rationale="alasan uji",
    )
