"""Tahap 1 — Perencana.

Dari sinyal Tier-1 (gratis, dari warehouse) + memori → rencana penyelidikan:
hipotesis, probe terurut, dan pagu kredit yang diminta.

**Kenapa tahap ini ada.** Data Sectors berbayar dan jatah kami 1.000 kredit.
Menyelidiki satu emiten secara menyeluruh berarti menembak keenam jalur bukti —
mahal, dan sebagian besar sia-sia karena mayoritas emiten normal. Yang sulit
bukan menghitung skor, tapi memutuskan **bukti mana yang layak dibeli untuk
emiten ini, hari ini**. Itu keputusan kontekstual; aturan if-else pecah
menghadapi ragamnya. Agen ada untuk menghemat uang, bukan untuk terlihat
modern. ARCHITECTURE §1.

Perencana melihat katalog probe **beserta harga kreditnya** dan memilih di bawah
pagu. Pemilihan alat yang sadar biaya itulah yang jadi Angka 2. [AD-7]

Keluaran selalu JSON terstruktur lewat tool use — tidak pernah prosa. Kalau LLM
gagal menghasilkan yang lolos skema, `fallback_plan()` mengambil alih: rencana
berbasis aturan yang selalu bisa dipertahankan. Agen yang mati karena LLM
ngelantur melanggar AD-6.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import Hypothesis, Plan  # noqa: E402
from core.agent.memory import Recollection  # noqa: E402
from core.llm import JSONInvalid, LLMError  # noqa: E402
from core.probes.registry import DESCRIPTIONS, PROBES  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402
from tools.vocab_guard import periksa_teks  # noqa: E402

log = get_logger(__name__)

LARANGAN = (  # vocab-ok: instruksi larangan kepada model, wajib menyebut kata yang dilarang
    "- Kamu TIDAK memberi saran investasi dan tidak menyebut beli/jual/target harga."
)

PROMPT_VERSION = "planner-v1"

SYSTEM = """Kamu perencana investigasi risiko saham di Bursa Efek Indonesia.

Tugasmu BUKAN menilai saham. Tugasmu memutuskan bukti mana yang layak dibeli
untuk emiten ini hari ini, di bawah pagu kredit yang terbatas.

Aturan:
- Tiap probe berbiaya kredit. Kredit itu terbatas dan tidak bisa diisi ulang.
- Mulai dari probe yang paling mungkin menjawab pertanyaan terbesar, bukan yang
  paling lengkap. Investigasi yang jelas bersih harus murah.
- Minta pagu sesuai rencanamu, bukan sebesar-besarnya. Pagu berlebih tidak
  membuatmu lebih pintar, hanya lebih boros.
{LARANGAN}

Jawab hanya lewat tool 'jawab'."""

SYSTEM = SYSTEM.format(LARANGAN=LARANGAN)


def _catalog_lines(show_price: bool = True) -> str:
    """Katalog probe untuk perencana. `show_price=False` dipakai eval ablasi
    untuk mengukur apakah harga benar-benar mengubah pilihan. [AD-7]"""
    baris = []
    for name, probe in PROBES.items():
        harga = f" — biaya {probe.cost_estimate('AAAA')} kredit" if show_price else ""
        baris.append(f"- {name}{harga}: {DESCRIPTIONS.get(name, '')}")
    return "\n".join(baris)


def _signal_lines(signals: dict) -> str:
    if not signals:
        return "(tidak ada sinyal Tier-1 tersedia)"
    return "\n".join(f"- {k}: {v}" for k, v in sorted(signals.items()))


def build_prompt(symbol: str, as_of: date, signals: dict,
                 memory: Recollection | None, ceiling: int,
                 show_price: bool = True) -> str:
    bagian = [
        f"Emiten: {symbol}. Tanggal acuan: {as_of.isoformat()} (data bursa EOD).",
        "",
        "Sinyal Tier-1 yang sudah tersedia gratis:",
        _signal_lines(signals),
        "",
        "Probe yang bisa kamu pilih:",
        _catalog_lines(show_price),
        "",
        f"Pagu keras: {ceiling} kredit per investigasi. Minta sesuai rencanamu.",
    ]
    if memory:
        bagian += ["", "Riwayat:", memory.briefing(as_of)]
    bagian += [
        "",
        "Susun 1–3 hipotesis. Tiap hipotesis menyebut probe mana yang mengujinya "
        "dan prioritasnya (1 = paling dulu). Jelaskan di 'rationale' kenapa urutan "
        "itu yang kamu pilih untuk emiten ini.",
    ]
    return "\n".join(bagian)


def fallback_plan(symbol: str, signals: dict, ceiling: int) -> Plan:
    """Rencana berbasis aturan, dipakai kalau LLM gagal.

    Sengaja murah dan generik: dua probe termurah dulu. Bukan rencana terbaik,
    tapi selalu bisa dipertahankan — dan itulah gunanya fallback. [AD-6]
    """
    murah = sorted(PROBES.values(), key=lambda p: p.cost_estimate(symbol))[:2]
    diminta = min(ceiling, sum(p.cost_estimate(symbol) for p in murah) + 2)
    return Plan(
        hypotheses=[
            Hypothesis(
                id="h1",
                claim="Ada pola perdagangan tidak biasa yang belum terjelaskan",
                probes=[p.name for p in murah],  # type: ignore[misc]
                priority=1,
            )
        ],
        credit_budget_requested=diminta,
        rationale=("Rencana cadangan berbasis aturan: perencana LLM tidak menghasilkan "
                   "keluaran yang lolos skema, jadi investigasi dimulai dari dua probe "
                   "termurah dan diputuskan ulang setelah temuan pertama."),
    )


def plan(*, symbol: str, as_of: date, signals: dict, ceiling: int,
         llm, memory: Recollection | None = None,
         show_price: bool = True) -> tuple[Plan, bool]:
    """Susun rencana. Mengembalikan (rencana, dipakai_llm).

    Bendera kedua penting untuk eval: rencana cadangan tidak boleh dihitung
    sebagai bukti kecerdasan agen.
    """
    prompt = build_prompt(symbol, as_of, signals, memory, ceiling, show_price)
    try:
        hasil = llm.ask_json(Plan, system=SYSTEM, prompt=prompt,
                             prompt_version=PROMPT_VERSION, max_tokens=1500)
    except (JSONInvalid, LLMError) as exc:
        log.warning("perencana gagal untuk %s (%s) — memakai rencana cadangan", symbol, exc)
        return fallback_plan(symbol, signals, ceiling), False

    # LLM boleh menyebut probe yang tidak ada. Disaring di sini, bukan dipercaya:
    # probe karangan akan menjatuhkan penyelidik di tengah jalan.
    bersih: list[Hypothesis] = []
    for h in hasil.hypotheses:
        sah = [p for p in h.probes if p in PROBES]
        if sah:
            bersih.append(h.model_copy(update={"probes": sah}))
        else:
            log.info("hipotesis '%s' dibuang: tidak menyebut probe yang dikenal", h.id)

    if not bersih:
        log.warning("semua hipotesis %s menyebut probe tak dikenal — rencana cadangan", symbol)
        return fallback_plan(symbol, signals, ceiling), False

    return _sanitize(hasil.model_copy(update={"hypotheses": bersih})), True


NETRAL_RATIONALE = (
    "Alasan pemilihan probe dari perencana disaring karena memuat bahasa yang "
    "menyerempet saran transaksi. Keputusan probe dan pagu kreditnya tetap apa "
    "adanya; hanya teks penjelasnya yang diganti."
)
NETRAL_CLAIM = "Hipotesis disaring karena memuat bahasa yang menyerempet saran transaksi."


def _sanitize(rencana: Plan) -> Plan:
    """Saring teks bebas rencana terhadap larangan kosakata. [K5]

    `rationale` dan `claim` ditulis LLM dan ikut tersimpan di transkrip, yang
    dipindai `tools/vocab_guard.py` dan ditampilkan di UI. Model yang beralasan
    dengan baik pun bisa menulis "belum layak dibeli" — dan aturan lomba
    melarang produk memberi saran finansial, dengan sanksi diskualifikasi.

    Yang diganti hanya prosanya, tidak pernah keputusannya: probe yang dipilih
    dan pagu yang diminta adalah hasil penalaran yang sah dan tetap utuh.
    Penggantian dinyatakan terang-terangan, bukan disembunyikan.
    """
    ubah: dict = {}
    if periksa_teks(rencana.rationale):
        log.warning("rationale perencana disaring: memuat bahasa saran transaksi")
        ubah["rationale"] = NETRAL_RATIONALE
    hipotesis = []
    for h in rencana.hypotheses:
        if periksa_teks(h.claim):
            log.warning("claim hipotesis %s disaring", h.id)
            hipotesis.append(h.model_copy(update={"claim": NETRAL_CLAIM}))
        else:
            hipotesis.append(h)
    if any(a is not b for a, b in zip(hipotesis, rencana.hypotheses, strict=True)):
        ubah["hypotheses"] = hipotesis
    return rencana.model_copy(update=ubah) if ubah else rencana
