"""Sapuan Tier-1: sinyal pasar market-wide, target ≤6 kredit per hari bursa.

Ini yang dijalankan cron tiap sore. Lima panggilan menutup seluruh IDX:

    fetch-close                  harga penutupan semua ticker      1 kredit
    fetch-most-traded-stocks     paling ramai diperdagangkan       1 kredit
    fetch-companies-top-changes  penggerak harga terbesar          1 kredit
    fetch-suspensions            suspensi baru                     1 kredit
    fetch-filings                filing insider baru               1 kredit

Keluarannya dua: warehouse bertambah satu hari, dan `watchlist.json` berisi
kandidat yang layak diselidiki agen besok. Penyaringan kandidat memakai **hanya
data yang sudah ada di warehouse** — nol kredit tambahan. Itu inti anggaran:
Tier-1 gratis menentukan ke mana Tier-2 yang mahal dibelanjakan. [ARCHITECTURE §5]

Kenapa most-traded dan top-changes ditulis ke tabel yang sudah ada, bukan tabel
baru: `contracts/warehouse.sql` beku, dan bentuk barisnya memang sudah cocok —
most-traded punya (symbol, tanggal, volume, harga) seperti `daily_transaction`,
top-changes punya (symbol, harga terakhir) seperti `daily_close`. Menambah tabel
berarti permintaan perubahan kontrak untuk sesuatu yang tidak butuh perubahan.

    python -m core.ingest.tier1_market --as-of 2026-09-08 --run-dir runs/2026-09-08
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from core.console import setup_console
from core.ingest.warehouse import Warehouse
from core.sectors.client import CreditAwareClient
from core.sectors.errors import SectorsError, TransportUnavailable
from core.sectors.ledger import CreditLedger
from core.sectors.redact import get_logger
from core.sectors.routing import TIER1_SWEEP, cost_of

log = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]

# Endpoint → tabel warehouse tujuan. Urutan penting: fetch-close lebih dulu
# supaya kalender hari bursa terisi sebelum yang lain dipetakan.
SWEEP: tuple[tuple[str, str], ...] = (
    ("fetch-close", "daily_close"),
    ("fetch-most-traded-stocks", "daily_transaction"),
    ("fetch-companies-top-changes", "daily_close"),
    ("fetch-suspensions", "suspensions"),
    ("fetch-filings", "filings"),
)

WATCHLIST_SIZE = 15

# Bobot penyaringan kandidat. Sengaja kasar dan bisa dijelaskan: ini bukan skor
# PANTAU, cuma antrean "siapa yang layak dilihat agen lebih dulu". Skor
# sesungguhnya tetap dihitung enam probe.
BOBOT = {
    "volume_z": 0.40,
    "return_5d": 0.25,
    "return_20d": 0.15,
    "small_cap": 0.10,
    "peristiwa": 0.10,
}

SMALL_CAP_RP = 5_000_000_000_000  # Rp 5 T — batas kasar small/mid cap IDX


@dataclass
class SweepResult:
    as_of: date
    credits_spent: int = 0
    rows_written: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    def say(self, message: str) -> None:
        stamp = datetime.now(UTC).strftime("%H:%M:%S")
        self.lines.append(f"[{stamp}Z] {message}")
        log.info(message)

    @property
    def ok(self) -> bool:
        return not self.failures


def sweep(client: CreditAwareClient, wh: Warehouse, as_of: date) -> SweepResult:
    """Jalankan lima panggilan Tier-1 dan tuliskan hasilnya ke warehouse."""
    result = SweepResult(as_of=as_of)
    result.say(f"sapuan Tier-1 untuk {as_of}")

    for endpoint, table in SWEEP:
        params = _params_for(endpoint, as_of)
        try:
            rows, resp = client.rows(endpoint, params, phase="daily")
        except TransportUnavailable as exc:
            if client.offline:
                # Mode offline memang tidak boleh menyentuh jaringan. Ini
                # keadaan yang diminta, bukan kegagalan — penyaringan di bawah
                # tetap jalan dari warehouse dan exit code tetap 0.
                result.skipped.append(endpoint)
                result.say(f"  lewati {endpoint} (offline, belum ada di cache)")
                continue
            result.failures.append(f"{endpoint}: {exc}")
            result.say(f"  GAGAL {endpoint}: {exc}")
            continue
        except SectorsError as exc:
            # Satu endpoint gagal tidak menghentikan empat lainnya — data
            # separuh lebih berguna daripada tidak ada, dan kegagalannya tetap
            # dilaporkan supaya workflow jadi merah.
            result.failures.append(f"{endpoint}: {exc}")
            result.say(f"  GAGAL {endpoint}: {exc}")
            continue

        frame = _to_table(endpoint, rows, as_of)
        total = wh.write(table, frame) if len(frame) else 0
        result.credits_spent += resp.credits_spent
        result.rows_written[endpoint] = len(frame)
        asal = "cache" if resp.cached else f"{resp.credits_spent} kredit"
        result.say(f"  {endpoint:<28} {len(frame):>5} baris -> {table} "
                   f"(kini {total} baris, {asal})")

    result.say(f"total {result.credits_spent} kredit; {client.stats.summary()}")
    return result


def _params_for(endpoint: str, as_of: date) -> dict:
    hari = as_of.isoformat()
    if endpoint == "fetch-close":
        return {"date": hari}
    if endpoint == "fetch-companies-top-changes":
        return {"periods": "1d", "n_stock": 30}
    if endpoint == "fetch-most-traded-stocks":
        return {"start": hari, "end": hari, "n_stock": 30}
    return {"start": hari, "end": hari}


def _to_table(endpoint: str, rows: list, as_of: date) -> pd.DataFrame:
    """Baris respons → DataFrame berbentuk tabel warehouse tujuan."""
    records = [r.model_dump() for r in rows]
    if not records:
        return pd.DataFrame()

    if endpoint == "fetch-most-traded-stocks":
        return pd.DataFrame([{
            "trade_date": r.get("trade_date") or as_of, "symbol": r["symbol"],
            "close_price": r.get("price"), "volume": r.get("volume"), "market_cap": None,
        } for r in records])

    if endpoint == "fetch-companies-top-changes":
        return pd.DataFrame([{
            "trade_date": as_of, "symbol": r["symbol"], "close_price": r.get("last_close"),
        } for r in records if r.get("last_close") is not None])

    return pd.DataFrame(records)


# ── penyaringan kandidat — nol kredit ───────────────────────────────────────
def screen(wh: Warehouse, as_of: date, size: int = WATCHLIST_SIZE) -> list[dict]:
    """Antrean kandidat untuk agen, dihitung dari warehouse saja.

    Bukan skor PANTAU. Ini cuma urutan "siapa yang layak dilihat lebih dulu",
    dan sengaja memakai sinyal yang gratis — kalau penyaringannya sendiri
    berbayar, seluruh alasan keberadaan agen (menghemat kredit) runtuh.
    """
    harga = wh.frame("daily_close", as_of=as_of)
    if harga.empty:
        return []

    harga = harga.sort_values(["symbol", "trade_date"])
    trans = wh.frame("daily_transaction", as_of=as_of)
    profil = wh.frame("company_profile", as_of=as_of).set_index("symbol") \
        if wh.exists("company_profile") else pd.DataFrame()
    peristiwa = _peristiwa_terbaru(wh, as_of)

    baris = []
    for symbol, g in harga.groupby("symbol"):
        closes = g["close_price"].dropna().astype(float)
        if len(closes) < 6:
            continue
        sinyal = {
            "return_5d": _pct(closes, 5),
            "return_20d": _pct(closes, 20),
            "volume_z": _volume_z(trans, symbol),
            "small_cap": _small_cap(profil, symbol),
            "peristiwa": 1.0 if symbol in peristiwa else 0.0,
        }
        skor = sum(BOBOT[k] * _clip(v) for k, v in sinyal.items())
        baris.append({
            "symbol": symbol,
            "score": round(skor, 4),
            "signals": {k: (round(v, 4) if v is not None else None) for k, v in sinyal.items()},
            "alasan": _alasan(sinyal, symbol in peristiwa),
        })

    baris.sort(key=lambda r: -r["score"])
    return baris[:size]


def _pct(closes: pd.Series, sessions: int) -> float | None:
    if len(closes) <= sessions:
        return None
    awal = float(closes.iloc[-1 - sessions])
    return None if awal <= 0 else float(closes.iloc[-1]) / awal - 1


def _volume_z(trans: pd.DataFrame, symbol: str) -> float | None:
    if trans.empty:
        return None
    g = trans[trans["symbol"] == symbol].sort_values("trade_date")
    volumes = g["volume"].dropna().astype(float)
    if len(volumes) < 20:
        return None
    baseline = volumes.iloc[:-1]
    median = baseline.median()
    mad = (baseline - median).abs().median() * 1.4826
    return None if mad <= 0 else float((volumes.iloc[-1] - median) / mad)


def _small_cap(profil: pd.DataFrame, symbol: str) -> float | None:
    if profil.empty or symbol not in profil.index:
        return None
    cap = profil.loc[symbol, "market_cap"]
    return None if pd.isna(cap) else (1.0 if float(cap) < SMALL_CAP_RP else 0.0)


def _peristiwa_terbaru(wh: Warehouse, as_of: date, hari: int = 5) -> set[str]:
    batas = as_of - pd.Timedelta(days=hari).to_pytimedelta()
    keluar: set[str] = set()
    for tabel, kolom in (("suspensions", "start_date"), ("filings", "filing_date")):
        df = wh.frame(tabel, as_of=as_of)
        if df.empty:
            continue
        baru = df[pd.to_datetime(df[kolom]).dt.date >= batas]
        keluar |= set(baru["symbol"].tolist())
    return keluar


def _clip(value: float | None) -> float:
    """Normalisasi kasar ke 0–1. None = sinyal tidak tersedia, bukan nol."""
    if value is None:
        return 0.0
    return max(0.0, min(1.0, value / 6.0 if value > 1.5 else value))


def _alasan(sinyal: dict, ada_peristiwa: bool) -> str:
    bagian = []
    if (z := sinyal["volume_z"]) is not None and z >= 2:
        bagian.append(f"volume {z:.1f}σ di atas baseline")
    if (r := sinyal["return_5d"]) is not None and abs(r) >= 0.1:
        bagian.append(f"harga {r * 100:+.0f}% dalam 5 hari bursa")
    if sinyal["small_cap"] == 1.0:
        bagian.append("kapitalisasi kecil")
    if ada_peristiwa:
        bagian.append("ada suspensi/filing baru")
    return "; ".join(bagian) or "tidak ada sinyal menonjol"


# ── artefak run ─────────────────────────────────────────────────────────────
def write_run(run_dir: Path, result: SweepResult) -> None:
    """Tulis run.log dan watchlist.json — bukti cron berjalan, ber-timestamp. [T5]"""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.log").write_text("\n".join(result.lines) + "\n", encoding="utf-8")
    (run_dir / "watchlist.json").write_text(
        json.dumps({
            "as_of": result.as_of.isoformat(),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "credits_spent": result.credits_spent,
            "rows_written": result.rows_written,
            "skipped": result.skipped,
            "failures": result.failures,
            "candidates": result.candidates,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Sapuan Tier-1 harian PANTAU")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--warehouse", type=Path, default=None)
    ap.add_argument("--size", type=int, default=WATCHLIST_SIZE)
    ap.add_argument("--offline", action="store_true",
                    help="hanya pakai cache & warehouse; nol jaringan, nol kredit")
    args = ap.parse_args(argv)

    run_dir = args.run_dir or (ROOT / "runs" / args.as_of.isoformat())
    wh = Warehouse(args.warehouse)
    ledger = CreditLedger()

    biaya_terburuk = sum(cost_of(e) for e in TIER1_SWEEP)
    if not args.offline and ledger.remaining("daily") < biaya_terburuk:
        print(f"pagu fase 'daily' tinggal {ledger.remaining('daily')} kredit, "
              f"sapuan butuh {biaya_terburuk} — dihentikan sebelum memanggil apa pun.")
        return 2

    with CreditAwareClient(phase="daily", ledger=ledger, offline=args.offline,
                           run_id=args.as_of.isoformat()) as client:
        result = sweep(client, wh, args.as_of)

    result.candidates = screen(wh, args.as_of, args.size)
    result.say(f"watchlist: {len(result.candidates)} kandidat")
    for c in result.candidates[:5]:
        result.say(f"  {c['symbol']}  skor {c['score']:.3f}  {c['alasan']}")

    write_run(run_dir, result)
    print("\n".join(result.lines))
    print(f"\nartefak: {run_dir}")

    if not result.ok:
        # Cron yang gagal harus MERAH dan terlihat, bukan diam. [QA M4]
        print(f"\n{len(result.failures)} endpoint gagal:", *result.failures, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
