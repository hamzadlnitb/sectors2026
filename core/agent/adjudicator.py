"""Tahap 3 — Penilai.

Buku bukti → skor **deterministik** → narasi tersitasi → transkrip.

Di sinilah batas yang paling penting di seluruh sistem dijaga: **agen memutuskan
APA yang diselidiki, kode memutuskan BERAPA skornya.** LLM tidak menyentuh satu
pun angka di berkas ini. Kalau batas ini kabur, angka jadi bisa dikarang, dan
kredibilitas habis di depan juri praktisi pasar. [AD-4][K8]

`score_fn` dan `narrate_fn` disuntikkan supaya penilai bisa diuji tanpa lajur
lain, dan supaya eval bisa menukar salah satunya tanpa menyentuh orkestrasi.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import InvestigationTranscript, Plan  # noqa: E402
from core.agent.investigator import Investigation  # noqa: E402
from core.agent.memory import Recollection  # noqa: E402
from core.agent.transcript import build  # noqa: E402
from core.probes.registry import PROBES  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)


def baseline_credits(symbol: str) -> int:
    """Biaya investigasi menyeluruh — keenam probe dijalankan.

    Ini pembanding klaim penghematan kami, jadi ia tidak boleh ditulis tangan:
    dijumlahkan dari `cost_estimate` yang sama dengan yang dilihat perencana,
    supaya begitu biaya endpoint berubah, angka penghematan ikut jujur. [AD-7]
    """
    return sum(p.cost_estimate(symbol) for p in PROBES.values())


def adjudicate(*, symbol: str, as_of: date, plan: Plan, inv: Investigation,
               llm, memory: Recollection | None = None,
               score_fn=None, narrate_fn=None) -> InvestigationTranscript:
    """Rakit transkrip akhir dari hasil investigasi."""
    if score_fn is None:
        from core.scoring.composite import score as score_fn
    if narrate_fn is None:
        from core.narrative.generate import narrate as narrate_fn

    from core.scoring.facts import evidence_book

    composite = score_fn(inv.results)
    evidence = evidence_book(inv.results)

    try:
        narasi, sumber = narrate_fn(symbol=symbol, composite=composite,
                                    evidence=evidence, steps=inv.steps, llm=llm)
    except Exception as exc:  # noqa: BLE001 — narasi tidak boleh menjatuhkan
        # transkrip. Skor dan bukti sudah lengkap; yang hilang cuma prosanya.
        log.exception("narasi gagal untuk %s", symbol)
        narasi = (f"Ringkasan otomatis tidak tersedia ({type(exc).__name__}). "
                  f"Rincian lengkap ada di buku bukti dan daftar langkah.")
        sumber = "template"

    # Langkah adalah sumber kebenaran biaya: probe yang menyerah tetap membakar
    # kredit meski buktinya dikosongkan kontrak. [contracts/CHANGES.md C2]
    total = sum(s.credits_spent for s in inv.steps)

    return build(
        symbol=symbol, as_of=as_of, plan=plan, steps=inv.steps,
        evidence=evidence, composite=composite, narrative=narasi,
        narrative_source=sumber, credits_total=total,
        baseline_credits=max(total, baseline_credits(symbol)),
        memory_ref=memory.ref if memory else None,
    )
