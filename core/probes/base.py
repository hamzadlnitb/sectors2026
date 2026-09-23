"""Kontrak Probe: biaya, jalankan, entri bukti.

Probe adalah **alat agen**, bukan endpoint Sectors mentah. Satu probe membungkus
beberapa panggilan, menghitung satu sub-skor 0–100, dan mengembalikan bukti
terstruktur berikut biayanya. Enam probe = enam komponen skor di ARCHITECTURE §4.

Tiga aturan yang ditegakkan berkas ini, bukan diserahkan ke enam penulis probe:

1. **Point-in-time.** Probe hanya melihat warehouse lewat Context, dan Context
   membuka koneksi yang sudah tersaring ≤ as_of. Bocor lookahead = kalibrasi
   bobot Hamzah bohong. [contracts/CHANGES.md C1]
2. **Tidak ada nol diam-diam.** Data kurang → sub_score None + alasan yang bisa
   dibaca manusia. Nol yang tidak dijelaskan akan mencemari skor komposit tanpa
   ada yang sadar. Wrapper run() memaksa ini, termasuk saat probe melempar
   exception yang tidak diduga.
3. **Biaya jujur.** credits_spent adalah belanja yang BENAR-BENAR terjadi saat
   run — nol kalau semuanya dilayani warehouse. cost_estimate() yang dipakai
   perencana untuk menganggarkan adalah perkiraan terburuk: biaya kalau
   warehouse kosong sama sekali.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import EvidenceEntry, ProbeName, ProbeResult  # noqa: E402
from core.ingest.warehouse import Warehouse  # noqa: E402
from core.sectors import routing  # noqa: E402
from core.sectors.errors import BudgetExceeded, SectorsError  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)

WIB = timezone(timedelta(hours=7))

# Data Sectors bersifat EOD. EvidenceEntry.as_of menjawab "kapan data ini
# berlaku", bukan "kapan kita mengambilnya" — jadi penandanya penutupan bursa,
# bukan jam cron kita berjalan. [K7]
MARKET_CLOSE = time(16, 0)

# Tabel yang juga diisi sapuan Tier-1 — tapi cuma untuk ±30 emiten teramai hari
# itu (core/ingest/tier1_market.py). Di sini baris terbaru bisa berasal dari
# sapuan dan menutupi lubang di belakangnya, jadi "segar" berarti tanpa lubang,
# bukan sekadar baris terakhirnya baru. Tabel lain sengaja tidak ikut:
# broker_summary adalah agregat satu rentang bertanggal satu hari, jarang memang
# bentuknya, dan mencari lubang di sana berarti menarik ulang tiap investigasi.
DIISI_SAPUAN = frozenset({"daily_transaction", "daily_close"})


def stamp(day: date) -> datetime:
    """Tanggal bursa → penanda waktu berzona WIB. Datetime naif ditolak kontrak."""
    return datetime.combine(day, MARKET_CLOSE, tzinfo=WIB)


def _tanggal(nilai: Any) -> date | None:
    """Parameter `start` probe (ISO string, date, atau None) → date."""
    if nilai is None or isinstance(nilai, date):
        return nilai
    try:
        return date.fromisoformat(str(nilai)[:10])
    except ValueError:
        return None


def ramp(value: float, lo: float, hi: float) -> float:
    """Petakan nilai ke 0–100 linear antara lo dan hi, dipotong di kedua ujung.

    Sengaja linear dan berjangkar dua angka: kurva yang tidak bisa dijelaskan
    dalam 15 detik tidak layak masuk halaman Metodologi. ARCHITECTURE §6.
    """
    if hi == lo:
        return 0.0
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


def rupiah(value: float) -> str:
    """Format nilai rupiah untuk display bukti. Bukan pembulatan akuntansi —
    ini teks yang dibaca Rina di layar."""
    sign = "-" if value < 0 else ""
    v = abs(value)
    for batas, satuan in ((1e12, "T"), (1e9, "M"), (1e6, "jt"), (1e3, "rb")):
        if v >= batas:
            return f"{sign}Rp {v / batas:.1f} {satuan}".replace(".", ",")
    return f"{sign}Rp {v:.0f}"


def persen(value: float, digits: int = 0) -> str:
    return f"{value * 100:.{digits}f}%".replace(".", ",")


def sigma(value: float) -> str:
    return f"{value:.1f}σ".replace(".", ",")


@dataclass
class Context:
    """Yang diterima probe saat dijalankan — implementasi ProbeContext.

    Sengaja sempit: probe hanya boleh menyentuh data lewat pintu ini, supaya
    tidak ada jalur yang melewati ledger kredit. [AD-5]
    """

    as_of: date
    warehouse: Warehouse
    client: Any = None
    budget_remaining: int = 0
    phase: str = "daily"
    spent: int = 0
    """Kredit yang benar-benar terbakar sejauh ini dalam konteks ini."""
    fetched: list[str] = field(default_factory=list)

    # ── baca ────────────────────────────────────────────────────────────────
    def frame(self, table: str, where: str = "", params: list | None = None) -> pd.DataFrame:
        """Tabel warehouse sebagai DataFrame, SUDAH tersaring ≤ as_of."""
        return self.warehouse.frame(table, as_of=self.as_of, where=where, params=params)

    def symbol_frame(self, table: str, symbol: str, since: date | None = None,
                     date_column: str | None = None) -> pd.DataFrame:
        from core.ingest.warehouse import TABLES

        cut = date_column or TABLES[table].cut_column
        where, params = "symbol = ?", [symbol]
        if since and cut:
            where += f" AND {cut} >= ?"
            params.append(since)
        df = self.frame(table, where, params)
        return df.sort_values(cut) if cut and cut in df.columns else df

    def price_history(self, symbol: str, since: date | None = None) -> pd.DataFrame:
        """Riwayat harga satu emiten, dari tabel mana pun yang memilikinya.

        daily_transaction lebih dulu: sejak fetch-close dikeluarkan dari sapuan
        harian (1 kredit per halaman, ~32 halaman sehari), daily_close cuma
        memuat penggerak harga terbesar hari itu. Probe yang membacanya sendirian
        akan mengira emiten paling likuid sekalipun tidak punya riwayat.
        """
        from core.ingest.warehouse import price_frame

        df = price_frame(self.warehouse, as_of=self.as_of, symbol=symbol)
        if since is not None and not df.empty:
            df = df[pd.to_datetime(df["trade_date"]).dt.date >= since]
        return df.reset_index(drop=True)

    def sessions(self, lookback: int) -> list[date]:
        from core.ingest.warehouse import trading_days

        return trading_days(self.warehouse, self.as_of, lookback)

    def _tertinggal(self, table: str, existing: pd.DataFrame,
                    since: date | None = None) -> bool:
        """True kalau baris terbaru belum mencapai hari bursa terakhir ≤ as_of —
        atau, untuk tabel DIISI_SAPUAN, kalau ada sesi bursa yang bolong di
        jendela [since, as_of].

        Pembandingnya kalender bursa yang benar-benar ada di warehouse, bukan
        selisih hari kalender — kalau tidak, tiap Senin akan terbaca basi karena
        data Jumat berumur tiga hari, dan tiap libur bursa memicu tarikan yang
        tidak menghasilkan baris baru.

        Lubang dihitung mulai baris pertama emiten itu, bukan dari `since`:
        emiten yang baru tercatat di tengah jendela tidak kehilangan apa pun.
        Suspensi di tengah jendela memang terbaca bolong dan memicu satu tarikan
        per investigasi — harga yang wajar, karena justru emiten itu yang layak
        dilihat dengan data utuh.
        """
        from core.ingest.warehouse import TABLES, trading_days

        cut = TABLES[table].cut_column
        if existing.empty or not cut or cut not in existing.columns:
            return False
        sesi = trading_days(self.warehouse, self.as_of, 1)
        if not sesi:
            return False
        ada = set(pd.to_datetime(existing[cut], errors="coerce").dropna().dt.date)
        if not ada:
            return False
        if max(ada) < sesi[-1]:
            return True
        if table not in DIISI_SAPUAN:
            return False

        awal = max(since, min(ada)) if since else min(ada)
        jendela = trading_days(self.warehouse, self.as_of, (self.as_of - awal).days + 1)
        return any(d >= awal and d not in ada for d in jendela)

    # ── ambil kalau kurang ──────────────────────────────────────────────────
    def ensure(self, table: str, endpoint: str, params: dict, *,
               symbol: str | None = None, min_rows: int = 1,
               where: str = "", where_params: list | None = None,
               fresh: bool = False) -> int:
        """Isi warehouse dari Sectors kalau data yang dibutuhkan belum cukup.

        Mengembalikan kredit yang terbakar (0 kalau warehouse sudah cukup, kalau
        tidak ada klien, atau kalau pagu tidak mengizinkan). Probe tidak pernah
        memanggil client langsung — supaya penganggaran punya satu tempat.

        `fresh=True` untuk tabel deret harian: "cukup" berarti barisnya mencapai
        hari bursa terakhir, bukan sekadar banyak. Tanpa ini, emiten yang punya
        riwayat panjang tapi berhenti diperbarui dianggap lengkap selamanya —
        probe tidak pernah menembak API lagi, nol kredit terbakar, dan bukti yang
        dikutip diam-diam menua. Persis yang terjadi 8–22 Sep: seluruh kandidat
        watchlist berhenti di 7 Sep sementara skornya tetap dicetak tiap hari.

        Kalau pagu investigasi tidak cukup, probe TIDAK dipaksa gagal: ia
        melanjutkan dengan data warehouse seadanya dan, kalau memang kurang,
        menutup dengan unavailable_reason. Menyerah karena pagu adalah perilaku
        yang diminta kontrak, bukan kesalahan. [AD-6]
        """
        existing = self.frame(table, where, where_params)
        if len(existing) >= min_rows and not (
                fresh and self._tertinggal(table, existing, _tanggal(params.get("start")))):
            return 0
        if self.client is None:
            return 0

        cost = routing.cost_of(endpoint)
        if cost > self.budget_remaining:
            log.info("probe menyerah pada %s: butuh %d kredit, sisa pagu %d",
                     endpoint, cost, self.budget_remaining)
            return 0

        try:
            rows, resp = self.client.rows(endpoint, params, phase=self.phase, symbol=symbol)
        except (SectorsError, BudgetExceeded) as exc:
            log.warning("gagal mengisi %s dari %s: %s", table, endpoint, exc)
            return 0

        if rows:
            self.warehouse.write(table, rows)
        self.budget_remaining -= resp.credits_spent
        self.spent += resp.credits_spent
        self.fetched.append(endpoint)
        return resp.credits_spent


@dataclass
class Finding:
    """Hasil mentah satu probe sebelum dibungkus jadi ProbeResult."""

    sub_score: float | None = None
    evidence: list[EvidenceEntry] = field(default_factory=list)
    unavailable_reason: str | None = None

    @classmethod
    def unavailable(cls, reason: str) -> Finding:
        return cls(sub_score=None, unavailable_reason=reason)


class BaseProbe(ABC):
    """Induk enam probe. Menegakkan kontrak supaya subkelas cukup menghitung."""

    name: ProbeName
    component: str
    endpoints: tuple[str, ...] = ()
    """Endpoint yang DIBUTUHKAN kalau warehouse kosong. Dasar cost_estimate()."""

    def cost_estimate(self, symbol: str) -> int:
        """Perkiraan kredit SEBELUM dijalankan — skenario terburuk.

        Perencana memakai angka ini untuk menganggarkan, jadi ia harus jadi batas
        atas: kalau warehouse ternyata sudah terisi, biaya nyatanya nol dan agen
        terlihat lebih hemat dari yang diperkirakan. Kebalikannya — perkiraan
        yang terlalu rendah — membuat pagu tertembus di tengah investigasi.
        """
        return sum(routing.cost_of(e) for e in self.endpoints)

    def run(self, symbol: str, ctx: Context) -> ProbeResult:
        """Jalankan probe. Tidak pernah melempar; kegagalan jadi alasan tertulis."""
        before = ctx.spent
        try:
            finding = self._compute(symbol, ctx)
        except Exception as exc:  # noqa: BLE001 — kegagalan probe tidak boleh
            # menjatuhkan investigasi. Agen wajib bisa menyimpulkan dengan bukti
            # yang sudah terkumpul. [AD-6]
            log.exception("probe %s gagal pada %s", self.name, symbol)
            finding = Finding.unavailable(
                f"probe gagal dijalankan: {type(exc).__name__}: {exc}"[:200]
            )

        spent = ctx.spent - before
        if finding.sub_score is None and not finding.unavailable_reason:
            finding.unavailable_reason = "probe tidak mengembalikan alasan — dianggap gagal"
        return ProbeResult(
            probe=self.name,
            sub_score=None if finding.sub_score is None else round(finding.sub_score, 1),
            unavailable_reason=finding.unavailable_reason,
            evidence=finding.evidence if finding.sub_score is not None else [],
            credits_spent=spent,
        )

    @abstractmethod
    def _compute(self, symbol: str, ctx: Context) -> Finding:
        """Hitung sub-skor dan bukti. Boleh melempar; run() yang membungkusnya."""

    # ── pembangun bukti ─────────────────────────────────────────────────────
    def evidence(self, id_: str, label: str, value: Any, display: str, *,
                 endpoint: str, params: dict, as_of: date,
                 credits: int = 0) -> EvidenceEntry:
        """Satu entri buku bukti.

        source_transport diambil dari tabel perutean, bukan ditulis tangan:
        warehouse tidak menyimpan jejak transport per baris, jadi yang bisa kita
        nyatakan jujur adalah "endpoint ini dilayani jalur X di sistem kami".
        """
        return EvidenceEntry(
            id=id_, label=label, value=value, display=display, probe=self.name,
            source_endpoint=endpoint, source_params=params,
            source_transport=routing.transport_for(endpoint),
            as_of=stamp(as_of), credits_spent=credits,
        )


def last_session(df: pd.DataFrame, column: str = "trade_date") -> date | None:
    """Tanggal bursa terakhir yang benar-benar ada di data.

    Bukan as_of: as_of boleh jatuh di akhir pekan atau libur, dan probe tidak
    boleh berpura-pura ada perdagangan pada hari itu.
    """
    if df.empty or column not in df.columns:
        return None
    value = pd.to_datetime(df[column]).max()
    return None if pd.isna(value) else value.date()
