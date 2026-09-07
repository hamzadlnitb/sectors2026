"""Kontrak data antar lajur PANTAU.

Bentuk di berkas ini adalah kesepakatan bertiga. Baca contracts/README.md
sebelum mengubah apa pun. Beku total setelah 12 September 2026.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"

ProbeName = Literal[
    "broker_concentration", "volume_anomaly", "price_fundamental",
    "free_float", "foreign_flow", "structural",
]
ComponentCode = Literal["BCI", "VAS", "PFD", "FFS", "FRD", "SSS"]
Transport = Literal["rest", "mcp"]
Band = Literal["normal", "perhatian", "waspada", "sangat_waspada"]

PROBE_TO_COMPONENT: dict[str, str] = {
    "broker_concentration": "BCI",
    "volume_anomaly": "VAS",
    "price_fundamental": "PFD",
    "free_float": "FFS",
    "foreign_flow": "FRD",
    "structural": "SSS",
}

BAND_THRESHOLDS: list[tuple[int, str]] = [
    (0, "normal"), (30, "perhatian"), (60, "waspada"), (80, "sangat_waspada"),
]

DISCLAIMER = "PANTAU adalah alat informasi dan analisis, bukan saran investasi."


# ── Kontrak 2 — EvidenceEntry ────────────────────────────────────────────────
# Satu entri per angka yang BOLEH muncul di narasi. Narasi yang memuat angka
# tanpa padanan di sini ditolak validator. [AD-4]

class EvidenceEntry(BaseModel):
    id: str = Field(description="Stabil dan bisa ditebak, mis. 'bci.top3_share'")
    label: str = Field(description="Bahasa Indonesia, siap tampil di UI")
    value: float | int | str | None
    display: str = Field(description="Sudah terformat, mis. '78%' atau 'Rp 1,2 T'")
    probe: ProbeName
    source_endpoint: str = Field(description="Nama tool/endpoint Sectors")
    source_params: dict[str, Any]
    source_transport: Transport
    as_of: datetime = Field(description="Kapan data ini berlaku, bukan kapan diambil")
    credits_spent: int = Field(ge=0)


# ── Kontrak 1 — ProbeResult + Probe ──────────────────────────────────────────
# Melco → Hamzah.

class ProbeResult(BaseModel):
    probe: ProbeName
    sub_score: float | None = Field(default=None, ge=0, le=100)
    unavailable_reason: str | None = Field(
        default=None,
        description="Wajib diisi kalau sub_score None. Jangan pernah mengembalikan 0 diam-diam.",
    )
    evidence: list[EvidenceEntry] = Field(default_factory=list)
    credits_spent: int = Field(ge=0)


@runtime_checkable
class Probe(Protocol):
    name: ProbeName

    def cost_estimate(self, symbol: str) -> int:
        """Perkiraan kredit SEBELUM dijalankan. Dipakai perencana untuk menganggarkan."""
        ...

    def run(self, symbol: str, ctx: Any) -> ProbeResult: ...


# ── Kontrak 5 — ToolCatalogEntry ─────────────────────────────────────────────
# Melco → Hamzah. Harga ikut disajikan ke perencana; itu inti klaim MCP kita. [AD-7]

class ToolCatalogEntry(BaseModel):
    name: str
    transport: Transport
    description: str
    args_schema: dict[str, Any]
    credit_cost: int = Field(ge=0, le=3)


# ── Kontrak 3 — InvestigationTranscript ──────────────────────────────────────
# Hamzah → Nadhilla.

class Hypothesis(BaseModel):
    id: str
    claim: str
    probes: list[ProbeName]
    priority: int = Field(ge=1)


class Plan(BaseModel):
    hypotheses: list[Hypothesis]
    credit_budget_requested: int = Field(ge=0)
    rationale: str


class Step(BaseModel):
    step: int = Field(ge=1)
    hypothesis: str | None
    probe: ProbeName
    finding: Literal["confirmed", "refuted", "inconclusive"]
    next_action: Literal["continue", "escalate", "conclude"]
    new_probe: ProbeName | None = Field(
        default=None, description="Diisi hanya kalau next_action == 'escalate'"
    )
    reason: str
    credits_spent: int = Field(ge=0)
    credits_remaining: int = Field(ge=0)


class ComponentScore(BaseModel):
    code: ComponentCode
    sub_score: float | None = Field(default=None, ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    investigated: bool


class InvestigationTranscript(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    symbol: str
    as_of: date

    plan: Plan
    steps: list[Step]
    evidence: list[EvidenceEntry]
    components: list[ComponentScore]

    pantau_score: int = Field(ge=0, le=100)
    band: Band
    confidence: float = Field(
        ge=0, le=1, description="Bobot komponen yang benar-benar diselidiki"
    )

    credits_total: int = Field(ge=0)
    baseline_credits: int = Field(
        ge=0, description="Biaya kalau keenam probe dijalankan. Pembanding klaim penghematan."
    )

    narrative: str
    narrative_source: Literal["llm", "template"] = Field(
        description="'template' = validator sitasi menolak keluaran LLM. Tampilkan apa adanya."
    )
    memory_ref: str | None = Field(
        default=None, description="Investigasi sebelumnya untuk ticker ini, kalau ada"
    )
    disclaimer: str = DISCLAIMER
