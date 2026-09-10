"""Pagar agen. Agen dipagari keras, bukan dipercaya. [AD-6]

Empat pagar, dan satu aturan tentang apa yang terjadi kalau tertembus:

1. **Maks 8 langkah** (`PANTAU_MAX_STEPS`) — loop yang tidak bisa berhenti
   sendiri bukan agen, itu bug yang mahal.
2. **Timeout per langkah** (`PANTAU_STEP_TIMEOUT`) — satu probe yang menggantung
   tidak boleh menyandera cron malam hari.
3. **Nama probe wajib sah** — LLM boleh mengarang `probe_pump_and_dump`; kita
   tidak wajib mempercayainya.
4. **Satu probe hanya sekali per investigasi** — mengulang probe yang sama
   membakar kredit tanpa menambah bukti, dan `contracts/check.py` menolaknya.

Aturannya: **melewati pagar = investigasi ditutup dengan bukti yang sudah
terkumpul, bukan exception yang naik ke atas.** Karena itu berkas ini tidak
pernah melempar keluar. Ia mengembalikan `Verdict` yang bisa dibaca, dan
`run_probe()` membungkus kegagalan probe jadi `ProbeResult` beralasan.

Konsekuensi yang disengaja: agen yang ngelantur menghasilkan transkrip pendek
yang jujur, bukan traceback. Itu yang membuatnya layak jalan tanpa pengawasan
di cron 17:30 WIB.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_args

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import ProbeName, ProbeResult  # noqa: E402
from core.env import load_env  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)

DEFAULT_MAX_STEPS = 8
DEFAULT_STEP_TIMEOUT = 45.0

PROBE_NAMES: frozenset[str] = frozenset(get_args(ProbeName))
"""Diturunkan dari kontrak, tidak ditulis tangan — daftar yang disalin akan
menyimpang dari `contracts/schemas.py` diam-diam."""


def _env_number(name: str, default: float) -> float:
    load_env()
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        log.warning("%s '%s' bukan angka — memakai %s", name, raw, default)
        return default


def max_steps() -> int:
    return max(1, int(_env_number("PANTAU_MAX_STEPS", DEFAULT_MAX_STEPS)))


def step_timeout() -> float:
    return max(0.1, _env_number("PANTAU_STEP_TIMEOUT", DEFAULT_STEP_TIMEOUT))


@dataclass(frozen=True)
class Verdict:
    """Boleh atau tidak, berikut alasan yang layak masuk transkrip."""

    ok: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


BOLEH = Verdict(True)


@dataclass
class Guardrails:
    """Pagar satu investigasi. Menyimpan apa yang sudah dipakai."""

    limit_steps: int = field(default_factory=max_steps)
    timeout: float = field(default_factory=step_timeout)
    used: set[str] = field(default_factory=set)
    """Probe yang sudah dijalankan. Kunci pagar 'satu probe sekali'."""
    steps_taken: int = 0
    breaches: list[str] = field(default_factory=list)
    """Pagar yang tertembus, untuk dicatat di alasan penutupan."""

    # ── pagar ───────────────────────────────────────────────────────────────
    def may_step(self) -> Verdict:
        if self.steps_taken >= self.limit_steps:
            return self._breach(f"pagar {self.limit_steps} langkah tercapai")
        return BOLEH

    def may_run(self, probe: Any) -> Verdict:
        """Boleh menjalankan probe ini? Nama sah, belum pernah dipakai."""
        name = probe if isinstance(probe, str) else getattr(probe, "name", "")
        if name not in PROBE_NAMES:
            return self._breach(f"nama probe '{name}' tidak dikenal kontrak")
        if name in self.used:
            return self._breach(f"probe '{name}' sudah dijalankan di investigasi ini")
        return BOLEH

    def note_run(self, name: str) -> None:
        self.used.add(name)

    def note_step(self) -> None:
        self.steps_taken += 1

    def _breach(self, reason: str) -> Verdict:
        # Dicatat sekali saja: pagar yang sama ditanyakan berkali-kali dalam satu
        # loop, dan daftar alasan yang penuh duplikat tidak bisa dibaca siapa pun.
        if reason not in self.breaches:
            self.breaches.append(reason)
            log.info("pagar agen: %s", reason)
        return Verdict(False, reason)

    def summary(self) -> str:
        return "; ".join(self.breaches)

    # ── eksekusi berpagar ───────────────────────────────────────────────────
    def run_probe(self, probe: Any, symbol: str, ctx: Any) -> ProbeResult:
        """Jalankan satu probe di bawah timeout. Kegagalan probe tidak pernah
        melempar keluar; ia jadi `ProbeResult` beralasan.

        Prasyarat: `may_run(probe)` sudah dipanggil dan lolos — nama probe yang
        tidak dikenal kontrak ditolak di sana, bukan di sini, karena `ProbeResult`
        pun tidak bisa dibentuk untuk nama yang tidak ada di `ProbeName`.

        Probe asli sudah membungkus exception-nya sendiri (`BaseProbe.run`), tapi
        pagar ini tidak boleh bergantung pada sopan santun pemanggilnya: probe
        stub, probe pihak lain, dan probe yang menggantung di jaringan semuanya
        lewat sini. Timeout dijalankan di thread supaya portabel — `signal.alarm`
        hanya jalan di thread utama dan mati di Windows.
        """
        name = getattr(probe, "name", "?")
        if name not in PROBE_NAMES:  # pragma: no cover — dijaga may_run()
            raise ValueError(f"run_probe dipanggil untuk probe tak dikenal '{name}' — "
                             "panggil may_run() dulu")
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"probe-{name}") as pool:
            future = pool.submit(probe.run, symbol, ctx)
            try:
                hasil = future.result(timeout=self.timeout)
            except FutureTimeout:
                self._breach(f"probe '{name}' melewati timeout {self.timeout:.0f} detik")
                # Thread-nya dibiarkan selesai sendiri; yang penting investigasi
                # tidak ikut menggantung. Prosesnya toh berumur satu investigasi.
                pool.shutdown(wait=False, cancel_futures=True)
                return ProbeResult(
                    probe=name, sub_score=None, credits_spent=0,
                    unavailable_reason=f"probe melewati timeout {self.timeout:.0f} detik",
                )
            except Exception as exc:  # noqa: BLE001 — kegagalan probe tidak boleh
                # menjatuhkan investigasi; agen wajib bisa menyimpulkan.
                log.exception("probe %s melempar di luar pembungkusnya", name)
                self._breach(f"probe '{name}' melempar {type(exc).__name__}")
                return ProbeResult(
                    probe=name, sub_score=None, credits_spent=0,
                    unavailable_reason=f"probe gagal: {type(exc).__name__}: {exc}"[:200],
                )

        return _sanitize(hasil, name)


def _sanitize(hasil: Any, name: str) -> ProbeResult:
    """Pastikan yang kembali benar-benar ProbeResult untuk probe yang diminta.

    Validasi skema adalah pagar nomor 3, dan ia berlaku dua arah: bukan cuma
    keluaran LLM, tapi juga keluaran alat. Probe yang mengembalikan hasil probe
    lain akan mencemari komponen skor yang salah.
    """
    if not isinstance(hasil, ProbeResult):
        try:
            hasil = ProbeResult.model_validate(hasil)
        except Exception as exc:  # noqa: BLE001
            log.warning("keluaran probe %s tidak lolos skema: %s", name, exc)
            return ProbeResult(probe=name, sub_score=None, credits_spent=0,
                               unavailable_reason="keluaran probe tidak lolos skema ProbeResult")
    if hasil.probe != name:
        log.warning("probe %s mengembalikan hasil atas nama %s", name, hasil.probe)
        return ProbeResult(probe=name, sub_score=None, credits_spent=hasil.credits_spent,
                           unavailable_reason="probe mengembalikan hasil atas nama probe lain")
    return hasil
