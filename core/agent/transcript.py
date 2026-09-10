"""Rakit dan simpan transkrip investigasi.

Transkrip adalah produk akhir agen dan satu-satunya yang dilihat Nadhilla.
Ia harus bisa **diputar ulang**: juri menonton asinkron dan akan mengulang, jadi
membuka berkas yang sama dua kali wajib menghasilkan tampilan identik. Itu
sebabnya web tidak pernah memanggil LLM maupun Sectors saat runtime. [AD-1]
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import (  # noqa: E402
    DISCLAIMER,
    EvidenceEntry,
    InvestigationTranscript,
    Plan,
    Step,
)

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "investigations"


def build(*, symbol: str, as_of: date, plan: Plan, steps: list[Step],
          evidence: list[EvidenceEntry], composite, narrative: str,
          narrative_source: str, credits_total: int, baseline_credits: int,
          memory_ref: str | None = None) -> InvestigationTranscript:
    """Rakit transkrip. Melempar ValidationError kalau ada yang tidak konsisten —
    lebih baik gagal di sini daripada menulis transkrip cacat ke runs/."""
    return InvestigationTranscript(
        symbol=symbol,
        as_of=as_of,
        weights_version=composite.weights_version,
        plan=plan,
        steps=steps,
        evidence=evidence,
        components=composite.components,
        pantau_score=composite.pantau_score,
        band=composite.band,
        confidence=composite.confidence,
        credits_total=credits_total,
        baseline_credits=baseline_credits,
        narrative=narrative,
        narrative_source=narrative_source,  # type: ignore[arg-type]
        memory_ref=memory_ref,
        disclaimer=DISCLAIMER,
    )


def path_for(symbol: str, as_of: date, root: Path | None = None) -> Path:
    """runs/investigations/ABCD-YYYY-MM-DD.json — sama dengan format memory_ref,
    supaya UI bisa menautkan investigasi sebelumnya tanpa indeks terpisah."""
    return (root or RUNS) / f"{symbol}-{as_of.isoformat()}.json"


def save(transcript: InvestigationTranscript, root: Path | None = None) -> Path:
    path = path_for(transcript.symbol, transcript.as_of, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(transcript.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
