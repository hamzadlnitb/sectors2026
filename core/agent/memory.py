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

import json
import sys
from dataclasses import dataclass, field
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


# Komponen yang nilainya bergerak lambat: membelinya ulang tiap hari adalah
# kredit yang terbakar untuk angka yang sama. Free float diumumkan kuartalan;
# status suspensi/aksi korporasi berubah pada peristiwa, bukan harian. Angkanya
# adalah umur bukti (hari kalender) yang masih dianggap cukup segar.
LAMBAT_BERUBAH = {"FFS": 15, "SSS": 7}

KODE_KOMPONEN = ("BCI", "VAS", "PFD", "FFS", "FRD", "SSS")


def _umur_bukti(transkrip: dict, ids: list[str]) -> date | None:
    """Tanggal bukti TERTUA di antara `ids` — yang paling basi yang menentukan."""
    tanggal = []
    for e in transkrip.get("evidence", []):
        if e.get("id") not in ids:
            continue
        mentah = str(e.get("as_of") or "")[:10]
        try:
            tanggal.append(date.fromisoformat(mentah))
        except ValueError:
            continue
    return min(tanggal) if tanggal else None


@dataclass(frozen=True)
class Komponen:
    """Satu komponen skor dari investigasi sebelumnya, beserta umur buktinya."""

    kode: str
    sub_score: float | None
    as_of: date | None

    def usia(self, today: date) -> int | None:
        return (today - self.as_of).days if self.as_of else None


@dataclass(frozen=True)
class Recollection:
    """Investigasi sebelumnya atas emiten yang sama."""

    symbol: str
    as_of: date
    pantau_score: int
    band: str
    confidence: float
    credits_total: int
    components: dict[str, Komponen] = field(default_factory=dict)
    """Diisi dari `transcript_path` bila transkripnya masih ada di disk. Kosong
    bukan kesalahan: memori dari mesin lain, atau `runs/` yang sudah dipangkas,
    tetap menghasilkan briefing yang sah — hanya lebih dangkal."""

    @property
    def ref(self) -> str:
        """Format `memory_ref` yang diwajibkan kontrak: ABCD-YYYY-MM-DD."""
        return f"{self.symbol}-{self.as_of.isoformat()}"

    def _baris_komponen(self, today: date) -> str:
        """`VAS 100 (bukti per 22-09) · FFS 28 (per 07-09) · PFD/FRD belum pernah.`"""
        diperiksa, belum = [], []
        for kode in KODE_KOMPONEN:
            k = self.components.get(kode)
            if k is None or k.sub_score is None:
                belum.append(kode)
                continue
            umur = f" (bukti per {k.as_of:%d-%m})" if k.as_of else ""
            diperiksa.append(f"{kode} {k.sub_score:.0f}{umur}")
        bagian = " · ".join(diperiksa)
        if belum:
            bagian += (" · " if bagian else "") + "/".join(belum) + " belum pernah diperiksa"
        return bagian

    def _baris_segar(self, today: date) -> str:
        """Komponen lambat-berubah yang buktinya masih segar — jangan dibeli ulang.

        Ini satu-satunya kalimat di briefing yang benar-benar menghemat kredit:
        `free_float` dibeli ulang hampir tiap hari padahal angkanya kuartalan.
        """
        segar = []
        for kode, batas in LAMBAT_BERUBAH.items():
            k = self.components.get(kode)
            usia = k.usia(today) if k else None
            if k and k.sub_score is not None and usia is not None and usia <= batas:
                segar.append(f"{kode} (umur {usia} hari, batas {batas})")
        if not segar:
            return ""
        return ("Komponen yang bergerak lambat dan buktinya masih segar — tidak perlu "
                f"dibeli ulang: {', '.join(segar)}.")

    def briefing(self, today: date) -> str:
        """Beberapa baris untuk perencana. Ditulis sebagai perbandingan, bukan
        ringkasan, supaya rencana berikutnya diarahkan ke perubahan."""
        jarak = (today - self.as_of).days
        baris = [
            f"Emiten ini pernah diselidiki {jarak} hari lalu ({self.as_of.isoformat()}): "
            f"skor {self.pantau_score} ({self.band}), keyakinan {self.confidence:.0%}, "
            f"menghabiskan {self.credits_total} kredit."
        ]
        if self.components:
            baris.append("  " + self._baris_komponen(today) + ".")
            segar = self._baris_segar(today)
            if segar:
                baris.append(segar)
        baris.append("Fokuskan rencana pada APA YANG BERUBAH sejak saat itu, bukan "
                     "mengulang seluruh penyelidikan dari nol.")
        return "\n".join(baris)


def _komponen_dari_transkrip(path: str | None) -> dict[str, Komponen]:
    """Baca sub-skor + umur bukti dari transkrip yang tersimpan.

    Kegagalan apa pun — berkas hilang, JSON rusak, skema lama — menghasilkan
    dict kosong, bukan pengecualian: memori adalah pengarah rencana, dan rencana
    tanpa memori tetap sah. [AD-6]
    """
    if not path:
        return {}
    try:
        transkrip = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.debug("transkrip memori %s tidak terbaca (%s) — briefing tanpa komponen", path, exc)
        return {}
    keluar: dict[str, Komponen] = {}
    for komp in transkrip.get("components", []):
        kode = str(komp.get("code") or "")
        if not kode:
            continue
        skor = komp.get("sub_score")
        keluar[kode] = Komponen(
            kode=kode,
            sub_score=float(skor) if skor is not None else None,
            as_of=_umur_bukti(transkrip, list(komp.get("evidence_ids") or [])),
        )
    return keluar


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
                "SELECT symbol, as_of, pantau_score, band, confidence, credits_total, "
                "transcript_path FROM investigations WHERE symbol = ? AND as_of < ? "
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
            components=_komponen_dari_transkrip(row[6]),
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
