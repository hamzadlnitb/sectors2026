"""Empat lengan eval: agen, menyeluruh, urutan tetap, dan acak berpagu sama.

Yang diukur bukan "apakah agen pintar" melainkan **apakah keputusan perencanaannya
bernilai lebih daripada aturan sederhana**. Tanpa tiga lengan pembanding, klaim
penghematan kredit tidak bisa dibedakan dari "kami menjalankan lebih sedikit probe".

## Satuan biaya: kredit terhitung, bukan kredit terbakar

Eval dijalankan dengan `client=None`, jadi probe hanya membaca warehouse dan **nol
kredit benar-benar terbakar**. Yang dijumlahkan adalah `cost_estimate()` tiap probe
yang dijalankan — biaya seandainya warehouse kosong.

Ini bukan jalan pintas, ini satuan yang benar. Kredit terbakar bergantung pada apa
yang kebetulan sudah ada di cache saat eval berjalan, jadi ia mengukur keberuntungan
warehouse, bukan kualitas perencanaan. `cost_estimate()` adalah angka yang sama yang
dilihat perencana saat memilih, sehingga lengan-lengan ini dibandingkan dengan
penggaris yang sama. [AD-7]
"""

from __future__ import annotations

import itertools
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.schemas import (
    PROBE_TO_COMPONENT,  # noqa: E402
    ProbeResult,  # noqa: E402
)
from core.agent import planner as planner_mod  # noqa: E402
from core.agent.budget import Budget  # noqa: E402
from core.agent.guardrails import Guardrails  # noqa: E402
from core.agent.investigator import investigate  # noqa: E402
from core.probes.registry import PROBES  # noqa: E402
from core.scoring.composite import score  # noqa: E402
from core.scoring.weights import WEIGHTS  # noqa: E402

URUTAN_TETAP: tuple[str, ...] = tuple(PROBES)
"""Urutan registry — baseline naif yang paling mungkin ditulis orang tanpa agen."""


@dataclass
class ArmResult:
    arm: str
    symbol: str
    probes_run: list[str] = field(default_factory=list)
    results: dict[str, ProbeResult] = field(default_factory=dict)
    escalated: list[str] = field(default_factory=list)
    planner_llm: bool = True
    steps: int = 0

    @property
    def credits(self) -> int:
        """Kredit terhitung: biaya seandainya warehouse kosong."""
        return sum(PROBES[p].cost_estimate(self.symbol) for p in self.probes_run)

    @property
    def composite(self):
        return score(self.results)

    @property
    def band(self) -> str:
        return self.composite.band


def baseline_credits(symbol: str) -> int:
    return sum(p.cost_estimate(symbol) for p in PROBES.values())


def _jalankan(symbol: str, ctx, nama: list[str], arm: str) -> ArmResult:
    out = ArmResult(arm=arm, symbol=symbol)
    guards = Guardrails()
    for n in nama:
        ctx.budget_remaining = 999  # lengan pembanding tidak dibatasi pagu runtime
        out.results[n] = guards.run_probe(PROBES[n], symbol, ctx)
        out.probes_run.append(n)
    out.steps = len(out.probes_run)
    return out


def menyeluruh(symbol: str, ctx) -> ArmResult:
    """Keenam probe. Ini kebenaran pembanding untuk kesepakatan band."""
    return _jalankan(symbol, ctx, list(URUTAN_TETAP), "menyeluruh")


def urutan_tetap(symbol: str, ctx, pagu: int) -> ArmResult:
    """Urutan registry sampai pagu habis. Baseline naif yang harus dikalahkan agen."""
    dipilih, sisa = [], pagu
    for n in URUTAN_TETAP:
        biaya = PROBES[n].cost_estimate(symbol)
        if biaya > sisa:
            continue
        dipilih.append(n)
        sisa -= biaya
    return _jalankan(symbol, ctx, dipilih, "urutan_tetap")


def acak(symbol: str, ctx, pagu: int, seed: int = 0) -> ArmResult:
    """Pemilihan acak berbibit tetap dengan pagu sama.

    Bibit diturunkan dari simbol supaya hasilnya bisa diulang persis, tapi tetap
    berbeda antar emiten — bibit tunggal untuk semua emiten akan menghasilkan pola
    pilihan yang sama berulang kali dan membuat lengan ini bukan benar-benar acak.
    """
    rng = random.Random(f"{symbol}-{seed}")
    urutan = list(URUTAN_TETAP)
    rng.shuffle(urutan)
    dipilih, sisa = [], pagu
    for n in urutan:
        biaya = PROBES[n].cost_estimate(symbol)
        if biaya <= sisa:
            dipilih.append(n)
            sisa -= biaya
    return _jalankan(symbol, ctx, dipilih, "acak")


def agen(symbol: str, ctx, llm, *, as_of=None, show_price: bool = True,
         signals: dict | None = None) -> ArmResult:
    """Lengan agen sungguhan: perencana → penyelidik.

    `show_price=False` menyembunyikan harga kredit dari katalog perencana. Itu
    pembanding yang membuktikan klaim MCP kami punya isi: kalau perencana memilih
    sama saja tanpa melihat harga, "pemilihan tool sadar biaya" cuma sebutan. [AD-7]
    """
    from datetime import date

    hari = as_of or ctx.as_of or date.today()
    rencana, dari_llm = planner_mod.plan(
        symbol=symbol, as_of=hari, signals=signals or {},
        ceiling=25, llm=llm, memory=None, show_price=show_price,
    )
    budget = Budget.for_plan(rencana.credit_budget_requested)
    inv = investigate(symbol=symbol, plan=rencana, ctx=ctx, budget=budget,
                      llm=llm, guards=Guardrails())

    out = ArmResult(arm="agen" if show_price else "agen_tanpa_harga", symbol=symbol,
                    planner_llm=dari_llm, steps=len(inv.steps))
    out.probes_run = [s.probe for s in inv.steps]
    out.results = dict(inv.results)
    out.escalated = [s.new_probe for s in inv.steps if s.new_probe]
    return out


# ── oracle knapsack ─────────────────────────────────────────────────────────
# Ditambahkan setelah eval v1. Pada pagu tetap, "pilih probe supaya cakupan bobot
# maksimum" adalah knapsack — punya jawaban optimal yang bisa dihitung tanpa LLM.
# Lengan ini ada supaya kita tahu plafonnya, dan supaya kita berhenti mengklaim
# kecerdasan di ruang yang ternyata tertutup. Kalau agen ≈ oracle, nilai LLM bukan
# di pemilihan himpunan; kalau agen < oracle, kita tahu persis berapa yang hilang.


def _bobot(nama: str) -> float:
    return WEIGHTS.get(PROBE_TO_COMPONENT[nama], 0.0)


def himpunan_optimal(symbol: str, pagu: int) -> tuple[str, ...]:
    """Himpunan probe dengan cakupan bobot tertinggi di bawah pagu.

    Enumerasi penuh: enam probe berarti 63 kombinasi, jadi tidak perlu dynamic
    programming dan hasilnya benar-benar optimal, bukan hampiran greedy.
    """
    terbaik: tuple[float, tuple[str, ...]] = (-1.0, ())
    for r in range(1, len(PROBES) + 1):
        for kombinasi in itertools.combinations(PROBES, r):
            biaya = sum(PROBES[n].cost_estimate(symbol) for n in kombinasi)
            if biaya > pagu:
                continue
            cakupan = sum(_bobot(n) for n in kombinasi)
            if cakupan > terbaik[0]:
                terbaik = (cakupan, kombinasi)
    return terbaik[1]


def oracle(symbol: str, ctx, pagu: int) -> ArmResult:
    """Batas atas: himpunan optimal pada pagu yang sama. Tanpa LLM sama sekali."""
    return _jalankan(symbol, ctx, list(himpunan_optimal(symbol, pagu)), "oracle")
