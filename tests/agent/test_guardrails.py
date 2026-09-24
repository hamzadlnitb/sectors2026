"""Pagar agen harus benar-benar memagari, bukan mendokumentasikan niat.

Nol jaringan, nol kunci API. [AD-1]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import ProbeResult  # noqa: E402
from core.agent.guardrails import Guardrails  # noqa: E402


class ProbeMenggantung:
    """Probe yang menggantung lebih lama dari timeout — persis kasus yang
    pagar #2 janjikan tidak boleh menyandera cron."""

    name = "volume_anomaly"

    def __init__(self, detik: float) -> None:
        self.detik = detik
        self.selesai = False

    def run(self, symbol: str, ctx) -> ProbeResult:
        time.sleep(self.detik)
        self.selesai = True
        return ProbeResult(probe=self.name, sub_score=99.0, credits_spent=7)


def test_timeout_kembali_sebelum_probe_selesai():
    """Regresi B1: `with ThreadPoolExecutor(...)` memanggil shutdown(wait=True)
    saat keluar blok, sehingga ia MENUNGGU thread yang menggantung — membatalkan
    shutdown(wait=False, cancel_futures=True) yang dipanggil di dalamnya.

    Akibatnya `run_probe` baru kembali setelah probe selesai, berapa pun
    timeout-nya. Pagar #2 tidak pernah menegakkan apa pun, dan satu probe yang
    menggantung di jaringan bisa menyandera cron 17:30 semalaman.
    """
    probe = ProbeMenggantung(2.0)
    guards = Guardrails(timeout=0.2)

    mulai = time.monotonic()
    hasil = guards.run_probe(probe, "FIXA", ctx=None)
    lewat = time.monotonic() - mulai

    assert lewat < 1.0, f"run_probe menunggu {lewat:.2f}s — timeout tidak menggigit"
    assert hasil.sub_score is None
    assert hasil.credits_spent == 0
    assert "timeout" in (hasil.unavailable_reason or "")
    assert guards.breaches, "pelanggaran pagar wajib tercatat untuk alasan penutupan"


def test_pesan_timeout_tidak_membulatkan_jadi_nol():
    """Bonus B1: f"{0.5:.0f}" mencetak "0 detik" — pesan yang membuat operator
    mengira timeout-nya nol, bukan setengah detik."""
    probe = ProbeMenggantung(2.0)
    guards = Guardrails(timeout=0.5)
    hasil = guards.run_probe(probe, "FIXA", ctx=None)
    assert "0 detik" not in (hasil.unavailable_reason or "")
    assert "0,5" in (hasil.unavailable_reason or "") or "0.5" in (hasil.unavailable_reason or "")


def test_probe_normal_tetap_lewat_tanpa_disentuh():
    """Pagar tidak boleh mengubah hasil probe yang sehat."""

    class ProbeCepat:
        name = "free_float"

        def run(self, symbol, ctx):
            return ProbeResult(probe=self.name, sub_score=42.0, credits_spent=1)

    guards = Guardrails(timeout=5.0)
    hasil = guards.run_probe(ProbeCepat(), "FIXA", ctx=None)
    assert hasil.sub_score == 42.0
    assert hasil.credits_spent == 1
    assert not guards.breaches
