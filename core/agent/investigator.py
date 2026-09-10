"""Tahap 2 — Penyelidik.

Loop: jalankan probe → evaluasi temuan → putuskan lanjut / dalami / berhenti.
Tiap putaran menghasilkan satu `Step`, dan rangkaian Step itulah yang membuat
penalaran agen bisa ditonton. ARCHITECTURE §3.

Empat perilaku yang harus benar-benar mungkin terjadi di sini — tanpa keempatnya
agen cuma if-else berbaju LLM:

* **perutean adaptif** — membuka jalur bukti di luar rencana lewat `escalate`
* **penghentian dini** — berhenti begitu bukti cukup, menghemat kredit
* **eskalasi** — minta tambahan pagu, dan `budget.py` boleh MENOLAK
* **memori** — rencana masuk sudah diarahkan riwayat oleh perencana

Yang memutuskan rute adalah LLM. Yang menjalankan probe dan menghitung angka
adalah kode. Batas itu tidak boleh kabur. [AD-4]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import Plan, ProbeName, ProbeResult, Step  # noqa: E402
from core.agent.budget import Budget  # noqa: E402
from core.agent.guardrails import Guardrails  # noqa: E402
from core.llm import JSONInvalid, LLMError  # noqa: E402
from core.probes.registry import DESCRIPTIONS, PROBES  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)

LARANGAN = (  # vocab-ok: instruksi larangan kepada model, wajib menyebut kata yang dilarang
    "- Kamu TIDAK memberi saran investasi dan tidak menyebut beli/jual/target harga."
)

PROMPT_VERSION = "investigator-v1"

SYSTEM = """Kamu penyelidik risiko saham di Bursa Efek Indonesia.

Satu probe baru saja dijalankan dan hasilnya ada di hadapanmu. Putuskan langkah
berikutnya.

Aturan:
- Tiap probe berbiaya kredit dan pagumu terbatas. Berhenti begitu bukti cukup
  untuk menyimpulkan — investigasi yang bersih harus murah.
- 'escalate' hanya kalau temuan ini menuntut jalur bukti yang TIDAK ada di
  rencana awal. Sebutkan probe barunya dan alasannya. Permintaan tambahan pagu
  boleh ditolak, dan kamu harus tetap bisa menyimpulkan tanpanya.
- 'conclude' kalau bukti sudah cukup, atau kalau probe tersisa tidak akan
  mengubah kesimpulan.
{LARANGAN}

Jawab hanya lewat tool 'jawab'."""

SYSTEM = SYSTEM.format(LARANGAN=LARANGAN)


class Decision(BaseModel):
    """Keputusan LLM per langkah. Sengaja sempit — ia memilih rute, bukan angka."""

    finding: str = Field(pattern="^(confirmed|refuted|inconclusive)$")
    next_action: str = Field(pattern="^(continue|escalate|conclude)$")
    new_probe: str | None = None
    extra_credits: int = Field(default=0, ge=0, le=25)
    reason: str


@dataclass
class Investigation:
    """Keadaan satu investigasi berjalan."""

    symbol: str
    steps: list[Step] = field(default_factory=list)
    results: dict[str, ProbeResult] = field(default_factory=dict)
    llm_decisions: int = 0
    fallback_decisions: int = 0
    stopped_by: str = "conclude"

    @property
    def escalations(self) -> int:
        return sum(1 for s in self.steps if s.next_action == "escalate")

    @property
    def granted_total(self) -> int:
        return sum(s.budget_granted for s in self.steps)


def _queue(plan: Plan) -> list[ProbeName]:
    """Antrean probe dari rencana: prioritas dulu, lalu urutan penulisan.

    Duplikat dibuang di sini, bukan dibiarkan sampai ke pagar: satu probe hanya
    boleh sekali per investigasi, dan menemukannya di awal lebih murah daripada
    membuang langkah untuk menabrak pagar.
    """
    urut: list[ProbeName] = []
    for h in sorted(plan.hypotheses, key=lambda h: h.priority):
        for p in h.probes:
            if p in PROBES and p not in urut:
                urut.append(p)
    return urut


def _hypothesis_for(plan: Plan, probe: str) -> str | None:
    for h in sorted(plan.hypotheses, key=lambda h: h.priority):
        if probe in h.probes:
            return h.id
    return None


def _describe(hasil: ProbeResult) -> str:
    if hasil.sub_score is None:
        return f"probe {hasil.probe} menyerah: {hasil.unavailable_reason}"
    bukti = "; ".join(f"{e.label}: {e.display}" for e in hasil.evidence) or "(tanpa rincian)"
    return f"probe {hasil.probe} → sub-skor {hasil.sub_score:.0f}/100. Bukti: {bukti}"


def _fallback_decision(hasil: ProbeResult, sisa_antrean: int, sisa_pagu: int) -> Decision:
    """Keputusan berbasis aturan kalau LLM gagal. Konservatif dan murah. [AD-6]"""
    if hasil.sub_score is None:
        finding = "inconclusive"
    elif hasil.sub_score >= 60:
        finding = "confirmed"
    else:
        finding = "refuted"
    lanjut = sisa_antrean > 0 and sisa_pagu > 0
    return Decision(
        finding=finding,
        next_action="continue" if lanjut else "conclude",
        reason=("Keputusan cadangan berbasis aturan: penyelidik LLM tidak menghasilkan "
                "keluaran yang lolos skema."),
    )


def _decide(*, symbol: str, hasil: ProbeResult, plan: Plan, antrean: list[str],
            budget: Budget, llm, inv: Investigation) -> Decision:
    prompt = "\n".join([
        f"Emiten: {symbol}.",
        f"Rencana awal: {plan.rationale}",
        "",
        f"Hasil langkah ini — {_describe(hasil)}",
        "",
        f"Probe yang masih mengantre: {', '.join(antrean) or '(kosong)'}",
        f"Probe yang belum pernah dijalankan: "
        f"{', '.join(p for p in PROBES if p not in inv.results) or '(tidak ada)'}",
        "",
        f"Sisa pagu: {budget.remaining} kredit. Ruang eskalasi sampai pagar keras: "
        f"{budget.headroom} kredit.",
        "",
        "Katalog probe beserta biayanya:",
        "\n".join(f"- {n} ({PROBES[n].cost_estimate(symbol)} kredit): {DESCRIPTIONS.get(n,'')[:110]}"
                  for n in PROBES if n not in inv.results),
    ])
    try:
        d = llm.ask_json(Decision, system=SYSTEM, prompt=prompt,
                         prompt_version=PROMPT_VERSION, max_tokens=800)
        inv.llm_decisions += 1
        return d
    except (JSONInvalid, LLMError) as exc:
        log.warning("penyelidik gagal di %s (%s) — keputusan cadangan", symbol, exc)
        inv.fallback_decisions += 1
        return _fallback_decision(hasil, len(antrean), budget.remaining)


def investigate(*, symbol: str, plan: Plan, ctx, budget: Budget, llm,
                guards: Guardrails | None = None) -> Investigation:
    """Jalankan loop penyelidikan. Tidak pernah melempar.

    Apa pun yang terjadi — LLM mati, probe gagal, pagu habis, pagar tertembus —
    fungsi ini mengembalikan `Investigation` yang bisa disimpulkan. Agen yang
    jatuh karena salah satu di antaranya melanggar AD-6.
    """
    guards = guards or Guardrails()
    inv = Investigation(symbol=symbol)
    antrean = _queue(plan)

    while antrean:
        boleh = guards.may_step()
        if not boleh:
            inv.stopped_by = boleh.reason
            log.info("investigasi %s ditutup pagar: %s", symbol, boleh.reason)
            break

        probe_name = antrean.pop(0)
        probe = PROBES[probe_name]

        izin = guards.may_run(probe)
        if not izin:
            log.info("probe %s dilewati: %s", probe_name, izin.reason)
            continue

        biaya = probe.cost_estimate(symbol)
        if not budget.can_afford(biaya) and budget.remaining <= 0:
            inv.stopped_by = f"pagu habis sebelum {probe_name}"
            break

        ctx.budget_remaining = budget.remaining
        guards.note_step()
        hasil = guards.run_probe(probe, symbol, ctx)
        guards.note_run(probe_name)
        inv.results[probe_name] = hasil
        terpakai = budget.charge(hasil.credits_spent)

        d = _decide(symbol=symbol, hasil=hasil, plan=plan, antrean=antrean,
                    budget=budget, llm=llm, inv=inv)

        # ── eskalasi ────────────────────────────────────────────────────────
        granted = 0
        new_probe: str | None = None
        alasan = d.reason
        if d.next_action == "escalate":
            kandidat = d.new_probe if d.new_probe in PROBES else None
            if kandidat is None or kandidat in inv.results or kandidat in antrean:
                # Eskalasi ke probe yang tidak ada, sudah dijalankan, atau sudah
                # mengantre bukan perutean adaptif — itu kebisingan. Diturunkan
                # jadi 'continue' supaya transkrip tidak mengaku beradaptasi.
                log.info("eskalasi %s ditolak: probe '%s' tidak sah", symbol, d.new_probe)
                d = d.model_copy(update={"next_action": "continue", "new_probe": None})
            else:
                minta = d.extra_credits or PROBES[kandidat].cost_estimate(symbol)
                grant = budget.preview(minta)
                granted = budget.commit(grant)
                alasan = f"{d.reason} [{grant}]"
                if granted > 0:
                    new_probe = kandidat
                    antrean.insert(0, kandidat)  # type: ignore[arg-type]
                else:
                    # Ditolak: agen WAJIB tetap bisa menyimpulkan. Langkah tetap
                    # tercatat sebagai 'continue' supaya aritmetika pagu utuh.
                    d = d.model_copy(update={"next_action": "continue", "new_probe": None})

        inv.steps.append(Step(
            step=len(inv.steps) + 1,
            hypothesis=_hypothesis_for(plan, probe_name),
            probe=probe_name,  # type: ignore[arg-type]
            finding=d.finding,  # type: ignore[arg-type]
            next_action=d.next_action,  # type: ignore[arg-type]
            new_probe=new_probe,  # type: ignore[arg-type]
            budget_granted=granted,
            reason=alasan[:1000],
            credits_spent=terpakai,
            credits_remaining=budget.remaining,
        ))

        if d.next_action == "conclude":
            inv.stopped_by = "conclude"
            break
    else:
        inv.stopped_by = "antrean habis"

    _seal(inv)
    return inv


def _seal(inv: Investigation) -> None:
    """Langkah terakhir WAJIB berbunyi 'conclude'.

    Kontrak menuntutnya, dan alasannya bukan formalitas: transkrip yang berakhir
    dengan 'continue' menyiratkan ada langkah berikutnya yang hilang. Kalau loop
    berhenti karena pagar atau antrean habis, langkah terakhir ditulis ulang —
    dan alasan penutupannya ikut dicatat supaya pembaca tahu ini penghentian
    paksa, bukan keputusan agen.
    """
    if not inv.steps:
        return
    akhir = inv.steps[-1]
    if akhir.next_action == "conclude":
        return
    inv.steps[-1] = akhir.model_copy(update={
        "next_action": "conclude",
        "new_probe": None,
        "reason": f"{akhir.reason} [ditutup: {inv.stopped_by}]"[:1000],
    })
