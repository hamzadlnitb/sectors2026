"""Memori investigasi per-emiten.

Tanpa memori, agen menyelidiki emiten yang sama dengan rencana yang sama tiap
hari — dan perencanaannya tidak bisa disebut adaptif, cuma deterministik yang
dibungkus LLM. Dengan memori, investigasi ulang dimulai dari pertanyaan yang
berbeda: **apa yang berubah sejak terakhir kali?**

Itu salah satu dari empat perilaku yang membedakan agen dari if-else berbaju
LLM, dan satu-satunya yang tidak bisa dipalsukan di video: ia hanya muncul
kalau ada riwayat sungguhan di basis data. ARCHITECTURE §3.

Tabelnya sudah didefinisikan `contracts/warehouse.sql` (`investigations`).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "memory.duckdb"

DDL = """
CREATE TABLE IF NOT EXISTS investigations (
    symbol          VARCHAR NOT NULL,
    as_of           DATE    NOT NULL,
    pantau_score    INTEGER,
    band            VARCHAR,
    confidence      DOUBLE,
    credits_total   INTEGER,
    transcript_path VARCHAR,
    PRIMARY KEY (symbol, as_of)
);
"""


@dataclass(frozen=True)
class Recollection:
    """Investigasi sebelumnya atas emiten yang sama."""

    symbol: str
    as_of: date
    pantau_score: int
    band: str
    confidence: float
    credits_total: int

    @property
    def ref(self) -> str:
        """Format `memory_ref` yang diwajibkan kontrak: ABCD-YYYY-MM-DD."""
        return f"{self.symbol}-{self.as_of.isoformat()}"

    def briefing(self, today: date) -> str:
        """Satu paragraf untuk perencana. Ditulis sebagai perbandingan, bukan
        ringkasan, supaya rencana berikutnya diarahkan ke perubahan."""
        jarak = (today - self.as_of).days
        return (
            f"Emiten ini pernah diselidiki {jarak} hari lalu ({self.as_of.isoformat()}): "
            f"skor {self.pantau_score} ({self.band}), keyakinan {self.confidence:.0%}, "
            f"menghabiskan {self.credits_total} kredit. Fokuskan rencana pada APA YANG "
            f"BERUBAH sejak saat itu, bukan mengulang seluruh penyelidikan dari nol."
        )


class Memory:
    """Riwayat investigasi. Sengaja tipis — tidak menyimpan transkrip penuh,
    hanya cukup untuk mengarahkan rencana berikutnya dan menautkan UI."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_DB

    def _connect(self):
        import duckdb

        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(self.path))
        con.execute(DDL)
        return con

    def recall(self, symbol: str, before: date) -> Recollection | None:
        """Investigasi terakhir atas emiten ini SEBELUM tanggal acuan.

        `before` bersifat ketat: investigasi hari yang sama tidak dihitung
        sebagai riwayat, kalau tidak kalibrasi ulang atas tanggal lampau akan
        melihat dirinya sendiri sebagai memori. [point-in-time]
        """
        try:
            con = self._connect()
        except Exception as exc:  # noqa: BLE001 — memori tidak boleh menjatuhkan investigasi
            log.warning("memori tidak bisa dibuka (%s) — investigasi lanjut tanpa riwayat", exc)
            return None
        try:
            row = con.execute(
                "SELECT symbol, as_of, pantau_score, band, confidence, credits_total "
                "FROM investigations WHERE symbol = ? AND as_of < ? "
                "ORDER BY as_of DESC LIMIT 1",
                [symbol, before],
            ).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return Recollection(
            symbol=row[0],
            as_of=row[1] if isinstance(row[1], date) else date.fromisoformat(str(row[1])),
            pantau_score=int(row[2] or 0), band=str(row[3] or ""),
            confidence=float(row[4] or 0.0), credits_total=int(row[5] or 0),
        )

    def remember(self, transcript, path: Path | None = None) -> None:
        """Catat hasil investigasi. Gagal mencatat tidak menjatuhkan apa pun —
        transkrip di `runs/` tetap sumber kebenaran."""
        try:
            con = self._connect()
        except Exception as exc:  # noqa: BLE001
            log.warning("memori tidak bisa ditulis (%s) — transkrip tetap tersimpan", exc)
            return
        try:
            con.execute("DELETE FROM investigations WHERE symbol = ? AND as_of = ?",
                        [transcript.symbol, transcript.as_of])
            con.execute(
                "INSERT INTO investigations VALUES (?, ?, ?, ?, ?, ?, ?)",
                [transcript.symbol, transcript.as_of, transcript.pantau_score,
                 transcript.band, transcript.confidence, transcript.credits_total,
                 str(path) if path else None],
            )
        finally:
            con.close()
