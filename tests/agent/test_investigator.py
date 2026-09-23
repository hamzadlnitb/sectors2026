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


def jalankan(plan, jawaban, *, pagu=None, guards=None):
    llm = FakeLLM(responses={"investigator-v1": jawaban})
    return investigate(symbol="FIXA", plan=plan, ctx=CtxPalsu(),
                       budget=pagu or Budget.for_plan(plan.credit_budget_requested, ceiling=25),
                       llm=llm, guards=guards or Guardrails(min_confidence=0.0))


def tanpa_pagar_keyakinan():
    """Pagar #5 punya tesnya sendiri di bawah. Tes perilaku lain mematikannya
    supaya yang diukur tetap satu hal — kalau tidak, tiap tes yang menyimpulkan
    cepat ikut menguji ambang keyakinan tanpa menyatakannya."""
    return Guardrails(min_confidence=0.0)


# ── perilaku 1: penghentian dini ────────────────────────────────────────────
def test_penghentian_dini_menyisakan_probe_yang_tidak_dibeli():
    out = jalankan(rencana("volume_anomaly", "free_float", "structural"),
                   [keputusan(next_action="conclude")])
    assert len(out.steps) == 1
    assert out.steps[0].next_action == "conclude"
    assert "structural" not in {s.probe for s in out.steps}


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


# ── pemotongan jatah token ──────────────────────────────────────────────────
# MiniMax mengeluarkan blok `thinking` sebelum `tool_use`, memakan jatah yang sama.
# Kalau habis di tengah thinking, respons pulang tanpa tool_use sama sekali.

def test_terpotong_dibedakan_dari_penolakan():
    from core.llm import LLM, Truncated

    class Blok:
        def __init__(self, tipe): self.type = tipe

    class Resp:
        content = [Blok("thinking")]
        stop_reason = "max_tokens"

    try:
        LLM._extract(Resp(), expect_tool=True)
    except Truncated as exc:
        assert "jatah token habis" in str(exc)
    else:
        raise AssertionError("pemotongan harus melempar Truncated")


def test_thinking_sebelum_tool_use_tetap_terbaca():
    from core.llm import LLM

    class Thinking:
        type = "thinking"

    class ToolUse:
        type = "tool_use"
        input = {"finding": "confirmed"}

    class Resp:
        content = [Thinking(), ToolUse()]
        stop_reason = "tool_use"

    assert LLM._extract(Resp(), expect_tool=True) == {"finding": "confirmed"}


def test_json_dipungut_saat_model_menjawab_teks_bukan_tool():
    """MiniMax kadang mengabaikan tool_choice dan menjawab teks berisi JSON.

    Membuangnya ke jalur cadangan berarti mengukur aturan, bukan agen.
    """
    from core.llm import LLM

    class Blok:
        def __init__(self, tipe, teks=""):
            self.type, self.text = tipe, teks

    class Resp:
        content = [Blok("thinking"), Blok("text", '```json\n{"finding": "refuted"}\n```')]
        stop_reason = "end_turn"

    assert LLM._extract(Resp(), expect_tool=True) == {"finding": "refuted"}


def test_teks_tanpa_json_tetap_dianggap_gagal():
    from core.llm import LLM, LLMError

    class Blok:
        def __init__(self, tipe, teks=""):
            self.type, self.text = tipe, teks

    class Resp:
        content = [Blok("text", "Maaf, saya tidak bisa membantu.")]
        stop_reason = "end_turn"

    try:
        LLM._extract(Resp(), expect_tool=True)
    except LLMError:
        pass
    else:
        raise AssertionError("teks tanpa JSON harus tetap gagal")


# ── larangan kosakata di alasan langkah [K5] ────────────────────────────────
def test_alasan_langkah_yang_menyerempet_saran_transaksi_disaring(rencana):
    """`Step.reason` ditulis LLM dan ikut ter-commit — jadi ia harus disaring
    seperti `Plan.rationale`, bukan dipercaya.

    Regresi: penyaringan sempat hanya dipasang di planner. Tiga transkrip hasil
    backfill 10–17 Sep lolos dengan kata 'beli' berdiri sendiri, dan karena cron
    menjalankan `make vocab` atas artefak baru SEBELUM commit, satu kalimat
    seperti itu cukup untuk menjatuhkan seluruh pipeline harian — sapuan dan
    investigasi hari itu ikut hangus.
    """
    from core.agent.investigator import NETRAL_ALASAN

    llm = FakeLLM(responses={"investigator-v1": [
        {"finding": "confirmed", "next_action": "conclude",
         "reason": "Volume melonjak, harga sudah tinggi dan bukan sinyal beli."},
    ]})
    inv = investigate(symbol="FIXA", plan=rencana, ctx=CtxPalsu(),
                      budget=Budget.for_plan(10, ceiling=25), llm=llm,
                      guards=tanpa_pagar_keyakinan())

    assert inv.steps, "investigasi harus menghasilkan setidaknya satu langkah"
    alasan = inv.steps[-1].reason
    assert NETRAL_ALASAN in alasan, "alasan bermasalah wajib diganti teks netral"
    # Keputusannya TIDAK boleh ikut berubah — yang disaring cuma prosanya.
    assert inv.steps[-1].finding == "confirmed"
    assert inv.steps[-1].next_action == "conclude"


def test_alasan_langkah_yang_bersih_dibiarkan_apa_adanya(rencana):
    """Penyaringan tidak boleh main hantam: alasan deskriptif yang sah adalah
    justru bukti agen bernalar, dan menggantinya akan menghapus isi transkrip."""
    bersih = "Z-score volume 23,1 sigma dan rasio 25,5 kali median baseline."
    llm = FakeLLM(responses={"investigator-v1": [
        {"finding": "confirmed", "next_action": "conclude", "reason": bersih},
    ]})
    inv = investigate(symbol="FIXA", plan=rencana, ctx=CtxPalsu(),
                      budget=Budget.for_plan(10, ceiling=25), llm=llm,
                      guards=tanpa_pagar_keyakinan())
    assert bersih in inv.steps[-1].reason


# ── pagar #5: keyakinan minimum sebelum menyimpulkan (D2) ───────────────────
def test_conclude_ditolak_saat_keyakinan_rendah_dan_masih_ada_probe_terjangkau():
    """Regresi D2: satu probe yang menjawab keras menghasilkan skor 100 dengan
    keyakinan 0,22, dan papan menampilkannya seotoritatif skor enam komponen.
    Riwayat NICK 30-85-56-71-36-100-64-0-52 dalam sembilan hari hampir seluruhnya
    artefak ini, bukan pergerakan emitennya.

    Bobot terbesar adalah BCI 0,25 — satu komponen tidak akan pernah mencapai
    ambang 0,4, jadi agen wajib membeli setidaknya satu probe lagi.
    """
    out = jalankan(rencana("volume_anomaly", "free_float", "structural"),
                   [keputusan(next_action="conclude"),
                    keputusan(next_action="conclude")],
                   guards=Guardrails(min_confidence=0.4))

    assert len(out.steps) >= 2, "conclude di langkah pertama harus ditolak pagar"
    assert out.steps[0].next_action == "continue", "keputusan berhenti diubah jadi lanjut"
    assert "keyakinan" in out.steps[0].reason, "penolakan pagar wajib terbaca di transkrip"
    # Temuan langkah itu sendiri TIDAK boleh ikut dibatalkan.
    assert out.steps[0].finding == "confirmed"


def test_conclude_diizinkan_saat_pagu_habis_walau_keyakinan_rendah():
    """Memaksa agen membeli yang tidak mampu ia beli bukan kejujuran, itu pagar
    lain yang bohong. Pagu pas untuk SATU probe (2 kredit): setelah itu tidak ada
    yang terbeli, jadi conclude harus lewat walau keyakinan cuma 0,22 — dan
    transkrip jujur soal keyakinannya yang rendah."""
    pagu = Budget.for_plan(2, ceiling=2)
    out = jalankan(rencana("volume_anomaly", "free_float", "structural"),
                   [keputusan(next_action="conclude")],
                   pagu=pagu, guards=Guardrails(min_confidence=0.4))

    assert out.steps[-1].next_action == "conclude"
    assert "keyakinan" not in out.steps[-1].reason


def test_prompt_penyelidik_memuat_bukti_semua_langkah_sebelumnya():
    """Regresi D1: prompt tiap langkah hanya memuat hasil probe BARUSAN, jadi
    keputusan `conclude` di langkah 3 dibuat tanpa tahu langkah 1 memberi
    100/100. Model lalu menebak dari rationale rencana — itu sebab transkrip
    memuat kalimat seperti "volume_anomaly sebelumnya sudah mengonfirmasi..."
    yang tidak pernah benar-benar ia baca.
    """
    terlihat: list[str] = []

    class LLMPerekam:
        def ask_json(self, model, *, system, prompt, prompt_version, max_tokens):
            terlihat.append(prompt)
            aksi = "conclude" if len(terlihat) >= 2 else "continue"
            return model.model_validate(keputusan(next_action=aksi))

    investigate(symbol="FIXA", plan=rencana("volume_anomaly", "free_float"),
                ctx=CtxPalsu(), budget=Budget.for_plan(10, ceiling=25),
                llm=LLMPerekam(), guards=tanpa_pagar_keyakinan())

    assert len(terlihat) >= 2
    kedua = terlihat[1]
    assert "Bukti terkumpul sejauh ini" in kedua
    assert "volume_anomaly" in kedua, "probe langkah 1 harus ikut di prompt langkah 2"
    assert "Skor sementara" in kedua, "skor komposit sementara wajib ikut"
    assert "BELUM diperiksa" in kedua, "komponen yang belum dilihat wajib disebut"


def test_langkah_pertama_menyatakan_belum_ada_bukti():
    """Blok konteks tidak boleh berbohong di langkah pertama."""
    from core.agent.investigator import Investigation, _konteks_bukti

    teks = _konteks_bukti(Investigation(symbol="FIXA"), "FIXA",
                          Budget.for_plan(10, ceiling=25))
    assert "Belum ada bukti" in teks


# ── B7: langkah tidak dibuang untuk probe yang tidak terbeli ────────────────
def test_probe_yang_tidak_terbeli_dilewati_bukan_dijalankan():
    """Regresi B7: syarat lama `not can_afford(biaya) and remaining <= 0`
    membuat probe 3 kredit TETAP dijalankan saat sisa 1 — satu langkah dan satu
    panggilan LLM terbakar untuk `unavailable`, dan transkrip memuat "probe
    menyerah" yang terbaca seperti kegagalan data, padahal itu aritmetika pagu.
    """
    palsu_mahal = ProbePalsu("structural", biaya=9)
    palsu_murah = ProbePalsu("free_float", biaya=1)

    llm = FakeLLM(responses={"investigator-v1": [keputusan(next_action="continue"),
                                                 keputusan(next_action="conclude")]})
    import core.agent.investigator as m
    PROBES_ASLI = m.PROBES
    m.PROBES = {"volume_anomaly": ProbePalsu("volume_anomaly", biaya=1),
                "structural": palsu_mahal, "free_float": palsu_murah}
    try:
        out = investigate(symbol="FIXA",
                          plan=rencana("volume_anomaly", "structural", "free_float", minta=3),
                          ctx=CtxPalsu(), budget=Budget.for_plan(3, ceiling=3),
                          llm=llm, guards=tanpa_pagar_keyakinan())
    finally:
        m.PROBES = PROBES_ASLI

    assert palsu_mahal.dipanggil == 0, "probe yang tidak terbeli tidak boleh dijalankan"
    assert "structural" not in {s.probe for s in out.steps}
    assert palsu_murah.dipanggil == 1, "probe murah berikutnya harus tetap dikejar"
