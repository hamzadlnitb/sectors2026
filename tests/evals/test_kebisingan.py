"""`--repeat N` — mengukur kebisingan model, bukan membaca ulang cache.

Menjaga D8/T9 dari AUDIT.md: `core/llm.py` menyimpan cache berkunci
`(system, messages, tools, prompt_version, max_tokens, temperature)`, jadi
menjalankan eval dua kali menghasilkan angka yang identik — bukan karena agennya
stabil, melainkan karena jalan kedua tidak pernah benar-benar terjadi.
`reports/agent-eval-ringkasan.md` menyimpulkan kebisingan ±6–12 pp dari DUA
jalan; angka itu tidak layak dikutip sampai tiap jalan menembus cache.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.llm import LLMError  # noqa: E402
from evals import agent_eval as ev  # noqa: E402


class LLMPerekam:
    """Mencatat tiap `prompt_version` yang benar-benar sampai ke model."""

    def __init__(self) -> None:
        self.versi: list[str] = []
        self.model = "perekam"

    def ask_json(self, schema, *, system, prompt, prompt_version, **kw):
        self.versi.append(prompt_version)
        raise LLMError("perekam tidak menjawab — jalur cadangan yang dipakai")

    def ask_text(self, *, system, prompt, prompt_version, **kw):
        self.versi.append(prompt_version)
        raise LLMError("perekam tidak menjawab")


def _ringkasan(hemat: float, sepakat: float, kredit: float, band: int = 4) -> dict:
    return {"lengan": {"agen": {"hemat_persen": hemat, "sepakat_persen": sepakat,
                                "kredit_rata2": kredit, "sepakat_band": band}}}


# ── pembungkus kunci cache ──────────────────────────────────────────────────

def test_akhiran_ditempel_ke_prompt_version():
    dalam = LLMPerekam()
    llm = ev.LLMBerlabel(dalam, "-r3")

    for panggil in (lambda: llm.ask_json(dict, system="s", prompt="p",
                                         prompt_version="planner-v1"),
                    lambda: llm.ask_text(system="s", prompt="p",
                                         prompt_version="narrator-v1")):
        with contextlib.suppress(LLMError):
            panggil()

    assert dalam.versi == ["planner-v1-r3", "narrator-v1-r3"]


def test_atribut_lain_diteruskan_apa_adanya():
    """Pembungkus harus tak terlihat selain di kunci cache."""
    assert ev.LLMBerlabel(LLMPerekam(), "-r1").model == "perekam"


def test_tiap_jalan_memakai_akhiran_berbeda(monkeypatch, tmp_path):
    """Inti D8: tiga jalan harus menghasilkan tiga kunci cache yang berbeda,
    kalau tidak jalan kedua dan ketiga cuma membaca jawaban jalan pertama."""
    perekam = LLMPerekam()
    monkeypatch.setattr(ev, "_llm", lambda offline: perekam)
    monkeypatch.setattr(ev, "muat", lambda: [{"symbol": "ASLI"}])
    monkeypatch.setattr(ev, "HASIL", tmp_path)

    ev.main(["--offline", "--repeat", "3", "--pekerja", "1"])

    akhiran = {v.rsplit("-", 1)[-1] for v in perekam.versi if "planner" in v}
    assert akhiran == {"r1", "r2", "r3"}


def test_jalan_tunggal_tidak_menambah_akhiran(monkeypatch, tmp_path):
    """Tanpa --repeat, perilaku dan kunci cache-nya harus persis seperti dulu."""
    perekam = LLMPerekam()
    monkeypatch.setattr(ev, "_llm", lambda offline: perekam)
    monkeypatch.setattr(ev, "muat", lambda: [{"symbol": "ASLI"}])
    monkeypatch.setattr(ev, "HASIL", tmp_path)

    ev.main(["--offline", "--pekerja", "1"])

    assert all(v in ("planner-v1", "investigator-v1") for v in perekam.versi), perekam.versi


# ── perhitungan kebisingan ──────────────────────────────────────────────────

def test_rentang_dihitung_lintas_jalan():
    k = ev.kebisingan([_ringkasan(70.0, 62.5, 4.0),
                       _ringkasan(64.0, 75.0, 5.5),
                       _ringkasan(68.0, 68.75, 4.5)])

    hemat = k["metrik"]["hemat_persen"]
    assert k["jalan"] == 3
    assert (hemat["min"], hemat["max"]) == (64.0, 70.0)
    assert hemat["rentang"] == 6.0
    assert hemat["simpangan"] is not None, "≥3 jalan punya simpangan baku"


def test_dua_jalan_belum_punya_simpangan_baku():
    """Dengan dua titik, simpangan baku bukan angka yang berarti — rentangnya ya."""
    k = ev.kebisingan([_ringkasan(70.0, 62.5, 4.0), _ringkasan(64.0, 75.0, 5.5)])

    assert k["metrik"]["hemat_persen"]["simpangan"] is None
    assert k["metrik"]["hemat_persen"]["rentang"] == 6.0


def test_satu_jalan_tidak_mengklaim_kebisingan():
    assert ev.kebisingan([_ringkasan(70.0, 62.5, 4.0)]) == {}


def test_laporan_menyebut_ambang_yang_tidak_boleh_dibaca_sebagai_beda():
    teks = ev.render_kebisingan(ev.kebisingan(
        [_ringkasan(70.0, 62.5, 4.0), _ringkasan(64.0, 75.0, 5.5)]))

    assert "6.0 pp" in teks
    assert "tidak\nboleh dibaca sebagai perbedaan nyata" in teks or \
           "tidak boleh dibaca sebagai perbedaan nyata" in teks
