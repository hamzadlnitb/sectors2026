"""Pagu kredit satu investigasi, berikut aturan eskalasinya.

Pagu adalah alasan keberadaan agen, jadi ia tidak boleh hidup di kepala
penyelidik. Berkas ini memegang tiga angka dan satu keputusan:

* **ceiling** — pagar keras per investigasi, 25 kredit (`PANTAU_MAX_CREDITS`).
  Tidak pernah dilampaui, apa pun yang diminta LLM. [AD-5][AD-6]
* **pool** — pagu yang benar-benar dikabulkan ke agen. Awalnya
  `Plan.credit_budget_requested`, bertambah hanya lewat eskalasi yang disetujui.
* **spent** — yang sudah terbakar.

Dan keputusan itu: **permintaan eskalasi boleh ditolak.** Ditolak bukan berarti
investigasi gagal — agen wajib menyimpulkan dengan bukti yang sudah terkumpul.
Kalau eskalasi selalu dikabulkan, pagu cuma hiasan dan salah satu dari empat
perilaku agentik kehilangan isinya. ARCHITECTURE §3.

`preview()` sengaja dipisah dari `commit()`. Penyelidik perlu tahu berapa yang
AKAN dikabulkan sebelum memutuskan apakah eskalasinya jadi dicatat: pagu yang
dikabulkan lalu tidak jadi dipakai membuat aritmetika `Step.budget_granted`
tidak nyambung, dan `contracts/check.py` menelusurinya langkah demi langkah.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.env import load_env  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)

DEFAULT_MAX_CREDITS = 25

ESCALATION_LIMIT = 2
"""Berapa kali eskalasi boleh dikabulkan dalam satu investigasi.

Bukan angka keramat: batas ini ada supaya agen tidak bisa menaikkan pagunya
sendiri selangkah demi selangkah sampai menyentuh ceiling. Dua kali cukup untuk
satu jalur bukti kejutan, dan yang ketiga hampir selalu berarti rencana awalnya
memang salah — lebih baik menyimpulkan lalu diselidiki ulang besok.
"""


def max_credits() -> int:
    """Pagar keras per investigasi. Dibaca saat dipanggil, bukan saat impor,
    supaya tes bisa menggesernya lewat monkeypatch."""
    load_env()
    raw = os.getenv("PANTAU_MAX_CREDITS", "").strip()
    try:
        value = int(raw) if raw else DEFAULT_MAX_CREDITS
    except ValueError:
        log.warning("PANTAU_MAX_CREDITS '%s' bukan angka — memakai %d", raw, DEFAULT_MAX_CREDITS)
        return DEFAULT_MAX_CREDITS
    return max(0, value)


@dataclass(frozen=True)
class Grant:
    """Jawaban atas satu permintaan eskalasi. Selalu membawa alasan tertulis —
    UI menampilkan 'minta berapa, dikabulkan berapa', bukan cuma hasil akhir."""

    requested: int
    granted: int
    reason: str

    @property
    def accepted(self) -> bool:
        return self.granted > 0

    @property
    def partial(self) -> bool:
        return 0 < self.granted < self.requested

    def __str__(self) -> str:
        if not self.accepted:
            return f"eskalasi {self.requested} kredit ditolak: {self.reason}"
        kata = "dikabulkan sebagian" if self.partial else "dikabulkan"
        return f"eskalasi {self.requested} kredit {kata} {self.granted}: {self.reason}"


@dataclass
class Budget:
    """Penganggaran satu investigasi. Satu-satunya tempat kredit bertambah."""

    ceiling: int
    pool: int
    spent: int = 0
    escalations: int = 0

    @classmethod
    def for_plan(cls, requested: int, *, ceiling: int | None = None) -> Budget:
        """Pagu awal = yang diminta perencana, dipotong pagar keras.

        Perencana boleh meminta lebih dari 25; yang berlaku tetap 25. Meminta
        terlalu besar bukan kesalahan yang perlu menjatuhkan investigasi.
        """
        cap = max_credits() if ceiling is None else max(0, ceiling)
        pool = max(0, min(requested, cap))
        if requested > cap:
            log.info("perencana meminta %d kredit, dipotong ke pagar %d", requested, cap)
        return cls(ceiling=cap, pool=pool)

    # ── posisi ──────────────────────────────────────────────────────────────
    @property
    def remaining(self) -> int:
        """Sisa yang boleh dibelanjakan sekarang."""
        return max(0, self.pool - self.spent)

    @property
    def headroom(self) -> int:
        """Ruang yang masih bisa dikabulkan lewat eskalasi, sampai pagar keras."""
        return max(0, self.ceiling - self.pool)

    def can_afford(self, cost: int) -> bool:
        return cost <= self.remaining

    # ── eskalasi ────────────────────────────────────────────────────────────
    def preview(self, amount: int) -> Grant:
        """Berapa yang AKAN dikabulkan. Murni — tidak mengubah apa pun.

        Urutan penolakan ditulis eksplisit supaya alasannya bisa dibaca manusia
        di transkrip, bukan cuma angka nol.
        """
        if amount <= 0:
            return Grant(amount, 0, "permintaan bukan angka positif")
        if self.escalations >= ESCALATION_LIMIT:
            return Grant(amount, 0,
                         f"batas {ESCALATION_LIMIT} eskalasi per investigasi sudah tercapai")
        if self.headroom <= 0:
            return Grant(amount, 0,
                         f"pagu sudah menyentuh pagar keras {self.ceiling} kredit")
        granted = min(amount, self.headroom)
        if granted < amount:
            return Grant(amount, granted,
                         f"hanya tersisa {self.headroom} kredit di bawah pagar {self.ceiling}")
        return Grant(amount, granted, "masih di bawah pagar dan beralasan")

    def commit(self, grant: Grant) -> int:
        """Kabulkan grant hasil preview. Mengembalikan tambahan pagu yang masuk."""
        if not grant.accepted:
            return 0
        added = min(grant.granted, self.headroom)
        self.pool += added
        self.escalations += 1
        log.info("eskalasi dikabulkan: +%d kredit, pagu jadi %d", added, self.pool)
        return added

    def refund(self, amount: int) -> int:
        """Tarik kembali pagu yang dikabulkan tapi tidak jadi dipakai.

        Terjadi kalau eskalasi dikabulkan lalu probe barunya ternyata tidak bisa
        dijalankan. Pagu yang menganggur harus dikembalikan, kalau tidak
        `credits_remaining` di transkrip mengaku punya sisa yang tidak pernah ada.
        """
        amount = max(0, min(amount, self.pool - self.spent))
        self.pool -= amount
        self.escalations = max(0, self.escalations - 1)
        return amount

    # ── belanja ─────────────────────────────────────────────────────────────
    def charge(self, credits: int) -> int:
        """Catat belanja yang sudah terjadi. Mengembalikan yang tercatat.

        Probe memutuskan sendiri untuk menyerah kalau `budget_remaining` tidak
        cukup, jadi belanja yang melebihi sisa seharusnya mustahil. Kalau tetap
        terjadi, yang salah adalah perkiraan biaya probe, bukan transkripnya:
        kelebihannya dipotong di sini supaya `credits_remaining` tidak pernah
        negatif, dan diteriakkan ke log. Angka sebenarnya tetap ada di
        data/credit_ledger.jsonl, yang memang sumber kebenaran biaya. [AD-5]
        """
        if credits <= 0:
            return 0
        tercatat = min(credits, self.remaining)
        if tercatat < credits:
            log.warning("belanja %d kredit melebihi sisa pagu %d — perkiraan biaya probe "
                        "terlalu rendah; %d kredit tidak masuk transkrip",
                        credits, self.remaining, credits - tercatat)
        self.spent += tercatat
        return tercatat
