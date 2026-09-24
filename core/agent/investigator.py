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

from contracts.schemas import PROBE_TO_COMPONENT, Plan, ProbeName, ProbeResult, Step  # noqa: E402
from core.agent.budget import Budget  # noqa: E402
from core.agent.guardrails import Guardrails  # noqa: E402
from core.llm import JSONInvalid, LLMError  # noqa: E402
from core.probes.registry import DESCRIPTIONS, PROBES  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402
from tools.vocab_guard import periksa_teks  # noqa: E402

log = get_logger(__name__)

NETRAL_ALASAN = (
    "Alasan langkah dari penyelidik disaring karena memuat bahasa yang menyerempet "
    "saran transaksi. Temuan, probe berikutnya, dan pagu kreditnya tetap apa adanya; "
    "hanya teks penjelasnya yang diganti."
)


def _saring_alasan(teks: str) -> str:
    """Saring `Step.reason` terhadap larangan kosakata. [K5]

    Cermin dari planner._sanitize, dan alasannya sama: `reason` ditulis LLM, ikut
    tersimpan di transkrip, dipindai tools/vocab_guard.py, dan ditampilkan di UI.
    Bedanya, yang ini sempat terlewat — sehingga `rationale` disaring sementara
    `reason` lolos apa adanya.

    Akibatnya bukan sekadar teks jelek. Cron menjalankan `make vocab` ATAS ARTEFAK
    BARU sebelum commit, jadi satu kalimat model yang memakai kosakata terlarang
    akan menjatuhkan seluruh pipeline harian hari itu — sapuan dan investigasi
    ikut hangus, persis pola kegagalan 21 September.

    Yang diganti hanya prosanya, tidak pernah keputusannya.
    """
    if not teks:
        return teks
    if periksa_teks(teks):
        log.warning("alasan langkah disaring: memuat bahasa saran transaksi")
        return NETRAL_ALASAN
    return teks


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


def _umur(entri) -> str:
    """" (per 22-09)" — umur bukti, supaya agen tahu apa yang sedang ia baca.

    Tanpa ini penyelidik tidak bisa membedakan broker summary hari ini dari yang
    berumur 15 hari, dan akan menyimpulkan dengan nada yang sama untuk keduanya.
    Persis kelas kesalahan yang membuat seluruh watchlist beku 8-22 Sep.
    """
    at = getattr(entri, "as_of", None)
    return f" (per {at:%d-%m})" if at is not None else ""


def _describe(hasil: ProbeResult) -> str:
    if hasil.sub_score is None:
        return f"probe {hasil.probe} menyerah: {hasil.unavailable_reason}"
    bukti = "; ".join(f"{e.label}: {e.display}{_umur(e)}" for e in hasil.evidence) \
        or "(tanpa rincian)"
    return f"probe {hasil.probe} → sub-skor {hasil.sub_score:.0f}/100. Bukti: {bukti}"


def _konteks_bukti(inv: Investigation, symbol: str, budget: Budget) -> str:
    """Semua bukti yang sudah terkumpul + skor sementara + apa yang belum dilihat.

    Tanpa blok ini, prompt tiap langkah hanya memuat hasil probe BARUSAN. Agen
    memutuskan `conclude` di langkah 3 tanpa tahu langkah 1 memberi 100/100 —
    dan karena ia tetap harus menulis alasan, ia menebak dari rationale rencana.
    Itu sebab transkrip berisi kalimat seperti "volume_anomaly sebelumnya sudah
    mengonfirmasi..." yang tidak pernah benar-benar ia baca.

    Semua angka di sini DETERMINISTIK dari score(inv.results). LLM tetap hanya
    memilih rute; ia tidak pernah mengarang skornya sendiri.
    """
    from core.scoring.composite import score

    if not inv.results:
        return "Belum ada bukti terkumpul — ini langkah pertama."

    komp = score(inv.results)
    baris = []
    for hasil in inv.results.values():
        if hasil.sub_score is None:
            baris.append(f"- {hasil.probe} → menyerah: {hasil.unavailable_reason}")
            continue
        rincian = "; ".join(f"{e.label}: {e.display}{_umur(e)}" for e in hasil.evidence)
        baris.append(f"- {hasil.probe} → {hasil.sub_score:.0f}/100. {rincian}")

    belum = [(c.code, c.weight) for c in komp.components if not c.investigated]
    belum.sort(key=lambda x: -x[1])
    belum_txt = ", ".join(
        f"{kode} bobot {bobot:.2f}"
        + next((f" ({PROBES[p].cost_estimate(symbol)} kredit)"
                for p, k in PROBE_TO_COMPONENT.items() if k == kode and p in PROBES), "")
        for kode, bobot in belum
    ) or "(tidak ada)"

    return "\n".join([
        "Bukti terkumpul sejauh ini:",
        *baris,
        f"Skor sementara: {komp.pantau_score} ({komp.band}), keyakinan "
        f"{komp.confidence:.0%} — {len(komp.investigated)}/6 komponen tercakup.",
        f"Komponen yang BELUM diperiksa: {belum_txt}.",
    ])


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
        _konteks_bukti(inv, symbol, budget),
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
                         prompt_version=PROMPT_VERSION, max_tokens=2500)
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
        if not budget.can_afford(biaya):
            # Syarat lama `and budget.remaining <= 0` membuat probe 3 kredit
            # TETAP dijalankan saat sisa 1: Context.ensure menolak tarikannya,
            # probe pulang `unavailable`, dan satu langkah + satu panggilan LLM
            # terbakar untuk hasil kosong. Transkrip lalu memuat "probe
            # menyerah" yang terbaca seperti kegagalan data, padahal itu
            # aritmetika pagu.
            terjangkau = [p for p in antrean
                          if budget.can_afford(PROBES[p].cost_estimate(symbol))]
            if terjangkau:
                log.info("probe %s dilewati: butuh %d kredit, sisa %d — lanjut ke %s",
                         probe_name, biaya, budget.remaining, terjangkau[0])
                continue
            inv.stopped_by = (f"pagu tidak cukup untuk probe tersisa "
                              f"(sisa {budget.remaining} kredit, {probe_name} butuh {biaya})")
            break

        ctx.budget_remaining = budget.remaining
        guards.note_step()
        hasil = guards.run_probe(probe, symbol, ctx)
        guards.note_run(probe_name)
        inv.results[probe_name] = hasil
        terpakai = budget.charge(hasil.credits_spent)

        d = _decide(symbol=symbol, hasil=hasil, plan=plan, antrean=antrean,
                    budget=budget, llm=llm, inv=inv)

        alasan = _saring_alasan(d.reason)

        # ── pagar #5: keyakinan minimum sebelum menyimpulkan ────────────────
        if d.next_action == "conclude":
            from core.scoring.composite import score as _score

            komp = _score(inv.results)
            terjangkau = [p for p in antrean
                          if budget.can_afford(PROBES[p].cost_estimate(symbol))]
            boleh_tutup = guards.may_conclude(komp.confidence, bool(terjangkau))
            if not boleh_tutup:
                # Diubah jadi `continue`, BUKAN dibatalkan: temuan langkah ini
                # tetap sah dan tetap tercatat. Yang ditolak cuma keputusan
                # berhentinya, dan penolakan itu ditulis terang di alasan supaya
                # pembaca transkrip melihat pagar bekerja, bukan agen berubah
                # pikiran tanpa sebab.
                d = d.model_copy(update={"next_action": "continue", "new_probe": None})
                alasan = f"[{boleh_tutup.reason}] {alasan}"

        # ── eskalasi ────────────────────────────────────────────────────────
        granted = 0
        new_probe: str | None = None
        if d.next_action == "escalate":
            kandidat = d.new_probe if d.new_probe in PROBES else None
            # Eskalasi berarti "aku butuh pagu LEBIH dari yang direncanakan untuk
            # mencapai probe ini" — bukan semata "probe ini di luar rencana".
            #
            # Versi pertama menolak setiap kandidat yang sudah mengantre, dan itu
            # membuat eskalasi mustahil menyala: perencana merencanakan tiga
            # hipotesis yang mengantre hampir semua probe, jadi nyaris setiap target
            # eskalasi sudah ada di antrean. Eval v1 mencatat NOL eskalasi dari 16
            # emiten — bukan karena agen tidak pernah butuh, tapi karena kodenya
            # menutup jalannya.
            #
            # Yang benar-benar bukan eskalasi: probe tak dikenal, probe yang sudah
            # dijalankan, dan probe yang toh sudah terbeli dengan pagu sekarang —
            # yang terakhir itu 'continue' biasa, tidak perlu tambahan pagu.
            sudah_terbeli = (
                kandidat is not None
                and kandidat in antrean
                and PROBES[kandidat].cost_estimate(symbol) <= budget.remaining
            )
            if kandidat is None or kandidat in inv.results or sudah_terbeli:
                log.info("eskalasi %s diturunkan: probe '%s' tidak butuh tambahan pagu",
                         symbol, d.new_probe)
                d = d.model_copy(update={"next_action": "continue", "new_probe": None})
            else:
                minta = d.extra_credits or PROBES[kandidat].cost_estimate(symbol)
                grant = budget.preview(minta)
                granted = budget.commit(grant)
                alasan = f"{alasan} [{grant}]"
                if granted > 0:
                    new_probe = kandidat
                    if kandidat in antrean:
                        antrean.remove(kandidat)  # pindah ke depan, jangan digandakan
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
        "reason": f"{_saring_alasan(akhir.reason)} [ditutup: {inv.stopped_by}]"[:1000],
    })
