"""Validator kontrak: setiap fixture wajib cocok dengan skema.

Dijalankan CI. Kalau gagal, artinya fixture dan kontrak sudah menyimpang —
perbaiki salah satunya sebelum ada yang membangun di atasnya.

    python3 contracts/check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.schemas import (  # noqa: E402
    BAND_THRESHOLDS, InvestigationTranscript, PROBE_TO_COMPONENT,
)

ROOT = Path(__file__).resolve().parent.parent


def band_for(score: int) -> str:
    band = BAND_THRESHOLDS[0][1]
    for threshold, name in BAND_THRESHOLDS:
        if score >= threshold:
            band = name
    return band


def check(path: Path) -> list[str]:
    errors: list[str] = []
    t = InvestigationTranscript.model_validate_json(path.read_text())

    # Band harus konsisten dengan skor — UI tidak boleh menampilkan dua kebenaran.
    if t.band != band_for(t.pantau_score):
        errors.append(f"band '{t.band}' tidak cocok dengan skor {t.pantau_score}")

    # Keyakinan = jumlah bobot komponen yang benar-benar diselidiki.
    investigated = sum(c.weight for c in t.components if c.investigated)
    if abs(investigated - t.confidence) > 0.01:
        errors.append(f"confidence {t.confidence} != bobot terselidiki {investigated:.2f}")

    if abs(sum(c.weight for c in t.components) - 1.0) > 0.01:
        errors.append("total bobot komponen bukan 1.0")

    # Tiap evidence_ids harus menunjuk entri bukti yang benar-benar ada. [AD-4]
    ids = {e.id for e in t.evidence}
    for c in t.components:
        for ref in c.evidence_ids:
            if ref not in ids:
                errors.append(f"komponen {c.code} menunjuk bukti tak dikenal '{ref}'")

    # Komponen yang diselidiki wajib punya bukti; yang tidak, wajib kosong.
    for c in t.components:
        if c.investigated and not c.evidence_ids:
            errors.append(f"komponen {c.code} ditandai terselidiki tapi tanpa bukti")
        if not c.investigated and c.sub_score is not None:
            errors.append(f"komponen {c.code} tidak diselidiki tapi punya sub_score")

    # Probe yang dijalankan harus tercermin di komponen yang ditandai terselidiki.
    ran = {PROBE_TO_COMPONENT[s.probe] for s in t.steps}
    ran |= {PROBE_TO_COMPONENT[s.new_probe] for s in t.steps if s.new_probe}
    marked = {c.code for c in t.components if c.investigated}
    if ran != marked:
        errors.append(f"probe dijalankan {sorted(ran)} != komponen terselidiki {sorted(marked)}")

    # Biaya harus berjumlah benar, dan penghematan tidak boleh diklaim palsu.
    if sum(e.credits_spent for e in t.evidence) != t.credits_total:
        errors.append("credits_total tidak sama dengan jumlah biaya bukti")
    if t.credits_total > t.baseline_credits:
        errors.append("credits_total melebihi baseline — tidak ada penghematan untuk diklaim")

    # Pagar agen. [AD-6]
    if len(t.steps) > 8:
        errors.append(f"{len(t.steps)} langkah melewati pagar 8")
    if t.credits_total > 25:
        errors.append(f"{t.credits_total} kredit melewati pagar 25 per investigasi")
    seen: set[str] = set()
    for s in t.steps:
        if s.probe in seen:
            errors.append(f"probe '{s.probe}' dijalankan lebih dari sekali")
        seen.add(s.probe)
    if t.steps and t.steps[-1].next_action != "conclude":
        errors.append("langkah terakhir tidak diakhiri 'conclude'")

    return errors


def main() -> int:
    paths = sorted((ROOT / "fixtures" / "transcripts").glob("*.json"))
    if not paths:
        print("tidak ada fixture ditemukan"); return 1
    failed = False
    for path in paths:
        try:
            errors = check(path)
        except Exception as exc:  # skema tidak cocok sama sekali
            print(f"✗ {path.name}: {exc}"); failed = True; continue
        if errors:
            failed = True
            print(f"✗ {path.name}")
            for e in errors:
                print(f"    {e}")
        else:
            print(f"✓ {path.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
