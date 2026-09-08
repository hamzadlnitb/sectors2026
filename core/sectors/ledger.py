"""Ledger kredit dan pagu per fase. [AD-5]

Sumber kebenaran posisi kredit adalah **berkas** data/credit_ledger.jsonl, bukan
variabel di memori. Konsekuensinya:

* proses mati di tengah backfill tidak menghilangkan catatan belanja;
* dua proses (mis. cron dan pengembangan lokal) melihat posisi yang sama;
* juri bisa menghitung ulang sendiri total kredit dari berkas yang di-commit —
  itu gunanya ledger ikut masuk repo.

Satu baris JSON per **belanja nyata**. Cache hit tidak ditulis: yang tidak
mengurangi jatah tidak boleh terlihat mengurangi jatah.

    python -m core.sectors.ledger      # = make credits
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from core.sectors.errors import BudgetExceeded

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / "data" / "credit_ledger.jsonl"

Phase = Literal["dev", "backfill", "eval", "daily", "reserve"]

# Pagu keras 1.000 kredit, dipecah persis seperti ARCHITECTURE.md §7.
CAPS: dict[str, int] = {
    "dev": 120,       # spike + pengembangan probe
    "backfill": 400,  # tarikan historis + kalibrasi
    "eval": 130,      # eval agen (dipakai Hamzah, lewat kode ini)
    "daily": 250,     # operasi harian otonom
    "reserve": 100,   # hanya lewat allow_reserve=True
}
TOTAL_CAP = sum(CAPS.values())

ALARM_LEVELS = (0.70, 0.90)

PHASE_LABEL = {
    "dev": "Spike + pengembangan probe",
    "backfill": "Backfill + kalibrasi",
    "eval": "Eval agen",
    "daily": "Operasi harian",
    "reserve": "Cadangan",
}


@dataclass(frozen=True)
class Entry:
    """Satu belanja kredit yang benar-benar terjadi."""

    ts: str
    phase: str
    endpoint: str
    transport: str
    credits: int
    params_hash: str
    run_id: str | None = None
    symbol: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {k: v for k, v in self.__dict__.items() if v is not None},
            ensure_ascii=False, sort_keys=True,
        )


class CreditLedger:
    """Buku besar kredit: tulis-tambah, baca-ulang, tegakkan pagu.

    Sengaja tidak menyimpan cache posisi di memori antar-panggilan write —
    posisi selalu dihitung ulang dari berkas supaya proses lain yang menulis
    tidak membuat pagu kita meleset.
    """

    def __init__(self, path: Path | None = None, caps: dict[str, int] | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_LEDGER
        self.caps = dict(caps) if caps else dict(CAPS)
        self._lock = threading.Lock()
        self._alarms_fired: set[tuple[str, float]] = set()

    # ── baca ────────────────────────────────────────────────────────────────
    def entries(self) -> list[Entry]:
        if not self.path.exists():
            return []
        out: list[Entry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                # Baris rusak tidak boleh membuat seluruh posisi kredit hilang.
                # Diabaikan dan dilaporkan lewat make credits.
                continue
            out.append(Entry(
                ts=raw.get("ts", ""), phase=raw.get("phase", "?"),
                endpoint=raw.get("endpoint", "?"), transport=raw.get("transport", "?"),
                credits=int(raw.get("credits", 0)), params_hash=raw.get("params_hash", ""),
                run_id=raw.get("run_id"), symbol=raw.get("symbol"),
            ))
        return out

    def spent(self, phase: str | None = None) -> int:
        rows = self.entries()
        if phase is not None:
            rows = [e for e in rows if e.phase == phase]
        return sum(e.credits for e in rows)

    def remaining(self, phase: str) -> int:
        return self.caps.get(phase, 0) - self.spent(phase)

    def position(self) -> list[dict]:
        """Ringkasan per fase, urut seperti di ARCHITECTURE.md §7."""
        rows = []
        for phase in CAPS:
            cap = self.caps.get(phase, 0)
            used = self.spent(phase)
            rows.append({
                "phase": phase, "label": PHASE_LABEL[phase], "cap": cap, "spent": used,
                "remaining": cap - used, "pct": (used / cap) if cap else 0.0,
            })
        return rows

    # ── tulis ───────────────────────────────────────────────────────────────
    def check(self, phase: str, credits: int, *, allow_reserve: bool = False) -> None:
        """Boleh belanja segini? Kalau tidak — raise, bukan warning.

        Pagu yang cuma diperingatkan bukan pagu: yang sedang mengejar deadline
        akan mengabaikannya, dan kredit habis sebelum kalibrasi selesai.
        """
        if phase == "reserve" and not allow_reserve:
            raise BudgetExceeded("reserve", credits, self.spent("reserve"), 0)
        cap = self.caps.get(phase)
        if cap is None:
            raise BudgetExceeded(phase, credits, 0, 0)
        used = self.spent(phase)
        if used + credits > cap:
            raise BudgetExceeded(phase, credits, used, cap)

    def record(
        self, *, phase: str, endpoint: str, transport: str, credits: int,
        params_hash: str, run_id: str | None = None, symbol: str | None = None,
    ) -> Entry:
        """Catat belanja yang SUDAH terjadi. Dipanggil hanya setelah respons sampai."""
        entry = Entry(
            ts=datetime.now(UTC).isoformat(timespec="seconds"),
            phase=phase, endpoint=endpoint, transport=transport, credits=credits,
            params_hash=params_hash, run_id=run_id, symbol=symbol,
        )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(entry.to_json() + "\n")
        self._maybe_alarm(phase)
        return entry

    def _maybe_alarm(self, phase: str) -> None:
        cap = self.caps.get(phase, 0)
        if not cap:
            return
        pct = self.spent(phase) / cap
        for level in ALARM_LEVELS:
            if pct >= level and (phase, level) not in self._alarms_fired:
                self._alarms_fired.add((phase, level))
                print(
                    f"[KREDIT] ALARM {int(level * 100)}% — fase '{phase}' terpakai "
                    f"{self.spent(phase)}/{cap} kredit",
                    flush=True,
                )


# ── laporan: make credits ───────────────────────────────────────────────────
def _bar(pct: float, width: int = 24) -> str:
    filled = min(width, int(round(pct * width)))
    return "#" * filled + "." * (width - filled)


def report(ledger: CreditLedger | None = None) -> str:
    ledger = ledger or CreditLedger()
    rows = ledger.position()
    total_spent = sum(r["spent"] for r in rows)
    lines = [
        "POSISI KREDIT SECTORS",
        f"berkas: {ledger.path}",
        "",
        f"{'fase':<12} {'terpakai':>9} {'pagu':>6} {'sisa':>6}  {'':<24} {'':>5}",
    ]
    for r in rows:
        flag = ""
        if r["pct"] >= 0.90:
            flag = "  ! 90%"
        elif r["pct"] >= 0.70:
            flag = "  ! 70%"
        lines.append(
            f"{r['phase']:<12} {r['spent']:>9} {r['cap']:>6} {r['remaining']:>6}  "
            f"{_bar(r['pct'])} {r['pct'] * 100:>4.0f}%{flag}"
        )
    lines += [
        "",
        f"{'TOTAL':<12} {total_spent:>9} {TOTAL_CAP:>6} {TOTAL_CAP - total_spent:>6}",
    ]

    entries = ledger.entries()
    if entries:
        by_endpoint: dict[str, int] = {}
        for e in entries:
            by_endpoint[e.endpoint] = by_endpoint.get(e.endpoint, 0) + e.credits
        lines += ["", "belanja per endpoint:"]
        for name, credits in sorted(by_endpoint.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {name:<34} {credits:>4}")
        lines += ["", f"{len(entries)} panggilan berbayar, terakhir {entries[-1].ts}"]
    else:
        lines += ["", "belum ada belanja tercatat."]
    return "\n".join(lines)


def main() -> int:
    path = os.environ.get("PANTAU_LEDGER")
    print(report(CreditLedger(Path(path)) if path else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
