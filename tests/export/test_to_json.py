"""Metrik jalur cadangan di `index.json`.

Menjaga D5 dari AUDIT.md: 10 dari 30 rencana ternyata cadangan berbasis aturan
dan 10 narasi memakai template, tapi angka itu tidak ada di `to_json`, README,
maupun eval. Tanpa angka ini kita tidak tahu apakah agen sedang beragen atau
sedang menjalankan if-else berbaju LLM — dan itu persis pertanyaan Track 1.

`Investigation.llm_decisions` dihitung di `investigator.py` tapi tidak pernah
masuk transkrip, dan `contracts/` beku sejak 12 Sep. Jadi yang dibaca adalah
kalimat yang ditulis jalur cadangan itu sendiri.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from contracts.schemas import InvestigationTranscript
from core.export.to_json import dari_llm, rekap_llm, summarize

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "transcripts" / "waspada.json"


def _transkrip(**ubah) -> InvestigationTranscript:
    isi = json.loads(FIXTURE.read_text(encoding="utf-8"))
    isi.update(ubah)
    return InvestigationTranscript.model_validate(isi)


def _dengan_alasan(*alasan: str) -> InvestigationTranscript:
    """Transkrip dengan langkah sebanyak `alasan`, memakai langkah pertama
    fixture sebagai cetakan supaya tetap lolos kontrak."""
    isi = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cetakan = isi["steps"][0]
    isi["steps"] = [{**cetakan, "step": i + 1, "reason": a}
                    for i, a in enumerate(alasan)]
    return InvestigationTranscript.model_validate(isi)


def test_rencana_llm_dibedakan_dari_rencana_cadangan():
    asli = _transkrip()
    rencana = dict(asli.plan)
    rencana["rationale"] = ("Rencana cadangan berbasis aturan: perencana LLM tidak "
                            "menghasilkan rencana yang sah.")

    assert dari_llm(asli)["planner_llm"] is True
    assert dari_llm(_transkrip(plan=rencana))["planner_llm"] is False


def test_keputusan_cadangan_dihitung_per_langkah():
    t = _dengan_alasan(
        "Volume melonjak jauh di atas baseline — perdalam ke konsentrasi broker.",
        "Keputusan cadangan berbasis aturan: penyelidik LLM tidak menghasilkan "
        "keputusan yang sah.",
        "Bukti sudah cukup untuk menyimpulkan.",
    )
    hasil = dari_llm(t)

    assert hasil["llm_decisions"] == 2
    assert hasil["fallback_decisions"] == 1


def test_gerbang_keyakinan_bukan_penanda_cadangan():
    """Awalan `[keyakinan ...]` dari pagar #5 ditempel di DEPAN alasan LLM —
    kalau dihitung sebagai cadangan, metriknya berbohong ke arah pesimis."""
    t = _dengan_alasan("[keyakinan 25% < 40%, masih ada probe terjangkau] "
                       "Volume melonjak — perdalam ke konsentrasi broker.")

    assert dari_llm(t)["llm_decisions"] == 1


def test_narasi_template_terbaca_bukan_llm():
    assert dari_llm(_transkrip(narrative_source="llm"))["narrative_llm"] is True
    assert dari_llm(_transkrip(narrative_source="template"))["narrative_llm"] is False


def test_rekap_menjumlahkan_lintas_investigasi():
    penuh = summarize(_dengan_alasan("Perdalam ke broker.", "Cukup."), "A-2026-09-22")
    campur = summarize(_dengan_alasan(
        "Keputusan cadangan berbasis aturan: penyelidik LLM tidak menghasilkan "
        "keputusan yang sah."), "B-2026-09-22")

    rekap = rekap_llm([penuh, campur])

    assert rekap["investigations"] == 2
    assert rekap["steps"] == 3
    assert rekap["llm_decisions"] == 2
    assert rekap["fallback_decisions"] == 1


def test_rekap_kosong_bukan_pembagian_nol():
    assert rekap_llm([]) == {"investigations": 0}


def test_ringkasan_memuat_blok_llm():
    """Halaman web membaca `index.json`, bukan transkrip satu per satu."""
    ringkas = summarize(_transkrip(), f"WSPD-{date(2026, 9, 22)}")
    assert set(ringkas["llm"]) == {
        "planner_llm", "llm_decisions", "fallback_decisions", "narrative_llm"}


# ── fixture tidak boleh bocor ke ekspor produksi (AUDIT B5) ─────────────────

def test_sumber_bawaan_hanya_transkrip_sungguhan():
    """FIXA/FIXB/FIXC/FIXD adalah placeholder UI, bukan investigasi.

    Selama ini `TRANSCRIPT_SOURCES` menggabungkan `fixtures/transcripts/` tanpa
    syarat, jadi keempatnya tampil di landing sebagai investigasi nyata —
    berdampingan dengan ASLI dan NICK, tanpa penanda apa pun. Begitu cron mulai
    mengekspor tiap malam, kebocoran ini jadi permanen. [AUDIT B5]
    """
    from core.export import to_json as ex

    assert ex.main_sources(with_fixtures=False) == [ex.REAL_SOURCE]
    assert ex.FIXTURE_SOURCE in ex.main_sources(with_fixtures=True)


def test_ekspor_bawaan_tidak_memuat_simbol_fix(tmp_path, monkeypatch):
    from core.export import to_json as ex

    monkeypatch.setattr(ex, "REAL_SOURCE", ex.ROOT / "runs" / "investigations")
    ringkasan, _ = ex.write_investigations(True, [ex.REAL_SOURCE])

    simbol = {r["symbol"] for r in ringkasan}
    assert simbol, "ada transkrip sungguhan untuk diperiksa"
    assert not any(s.startswith("FIX") for s in simbol), sorted(simbol)


def test_dengan_fixtures_memang_memuatnya():
    """Bendera itu ada gunanya — tes UI butuh keempat keadaan band."""
    from core.export import to_json as ex

    ringkasan, _ = ex.write_investigations(True, ex.main_sources(with_fixtures=True))

    assert {"FIXA", "FIXB", "FIXC"} <= {r["symbol"] for r in ringkasan}
