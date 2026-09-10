"""Skor komposit PANTAU — enam sub-skor jadi satu angka, band, dan keyakinan.

Tiga aturan yang ditegakkan di sini, karena ketiganya divalidasi
`contracts/check.py` dan akan menolak transkrip yang melanggarnya:

1. **Skor dihitung hanya atas komponen yang benar-benar diselidiki**, dibagi
   jumlah bobot yang tercakup. Agen boleh berhenti lebih awal; investigasi dua
   langkah tidak boleh dihukum seolah empat komponen lain bernilai nol.
2. **Keyakinan = jumlah bobot yang tercakup.** Angka ini yang membuat skor
   berkeyakinan rendah jujur di layar, bukan disembunyikan.
3. **Band selalu dari `band_for_score()`.** Satu-satunya tempat aturan ambang
   hidup. [contracts/CHANGES.md C1]

Probe yang menyerah (`sub_score` None) dihitung sebagai TIDAK diselidiki, bukan
sebagai nol. Nol berarti "sudah diperiksa, hasilnya bersih"; menyerah berarti
"belum tahu". Menyamakan keduanya akan menurunkan skor saham yang datanya
kebetulan tidak lengkap — persis kesalahan yang paling mudah lolos tanpa ada
yang sadar. [core/probes/base.py aturan 2]
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import (  # noqa: E402
    PROBE_TO_COMPONENT,
    ComponentScore,
    ProbeResult,
    band_for_score,
)

# Bobot hasil kalibrasi. Diimpor terpisah supaya lajur kalibrasi bisa
# menggantinya tanpa menyentuh berkas ini; nilai cadangan di bawah dipakai
# hanya sampai kalibrasi pertama mendarat, dan versinya menyebut dirinya
# sementara supaya tidak ada transkrip yang mengaku terkalibrasi padahal belum.
try:
    from core.scoring.weights import WEIGHTS, WEIGHTS_VERSION
except ImportError:  # pragma: no cover - hanya sebelum kalibrasi pertama
    WEIGHTS = {"BCI": 0.24, "VAS": 0.18, "PFD": 0.16, "FFS": 0.12,
               "FRD": 0.18, "SSS": 0.12}
    WEIGHTS_VERSION = "belum-terkalibrasi"


@dataclass(frozen=True)
class Composite:
    pantau_score: int
    band: str
    confidence: float
    components: list[ComponentScore]
    weights_version: str

    @property
    def investigated(self) -> list[str]:
        return [c.code for c in self.components if c.investigated]

    def __str__(self) -> str:
        return (f"{self.pantau_score} ({self.band}), keyakinan "
                f"{self.confidence:.0%}, {len(self.investigated)}/6 komponen")


def score(results: Mapping[str, ProbeResult],
          weights: Mapping[str, float] | None = None,
          weights_version: str | None = None) -> Composite:
    """Hitung skor komposit dari hasil probe.

    `results` dikunci nama probe. Probe yang tidak dijalankan cukup tidak ada di
    mapping — tidak perlu diisi None.
    """
    w = dict(weights or WEIGHTS)
    versi = weights_version or WEIGHTS_VERSION

    total = sum(w.values())
    if abs(total - 1.0) > 1e-6:
        # Bobot yang tidak berjumlah 1 membuat keyakinan berbohong: ia mengaku
        # "83% bobot tercakup" atas penyebut yang bukan 1. Dinormalisasi di sini
        # supaya kesalahan kalibrasi tidak menyelinap ke transkrip.
        if total <= 0:
            raise ValueError("bobot komponen tidak boleh berjumlah nol")
        w = {k: v / total for k, v in w.items()}

    komponen: list[ComponentScore] = []
    tertimbang = 0.0
    tercakup = 0.0

    for probe, kode in PROBE_TO_COMPONENT.items():
        bobot = w.get(kode, 0.0)
        hasil = results.get(probe)
        diselidiki = hasil is not None and hasil.sub_score is not None

        if diselidiki:
            tertimbang += bobot * hasil.sub_score
            tercakup += bobot

        komponen.append(ComponentScore(
            code=kode,  # type: ignore[arg-type]
            sub_score=hasil.sub_score if diselidiki else None,
            weight=round(bobot, 4),
            evidence_ids=[e.id for e in hasil.evidence] if diselidiki else [],
            investigated=diselidiki,
        ))

    # Nol komponen berhasil bukan kegagalan yang boleh melempar: agen wajib
    # tetap menghasilkan transkrip, dan keyakinan nol sudah mengatakan
    # semuanya kepada pembaca. [AD-6]
    nilai = 0 if tercakup <= 0 else round(tertimbang / tercakup)

    komponen.sort(key=lambda c: list(PROBE_TO_COMPONENT.values()).index(c.code))
    return Composite(
        pantau_score=int(nilai),
        band=band_for_score(int(nilai)),
        confidence=round(tercakup, 2),
        components=komponen,
        weights_version=versi,
    )
