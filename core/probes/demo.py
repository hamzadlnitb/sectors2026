"""make demo — jalankan enam probe di mesin bersih, tanpa API key, tanpa jaringan.

Ini jawaban atas kecurigaan pertama juri: *"apakah ini benar-benar bisa
dijalankan?"* `[AD-8]`. Bukan simulasi — probe yang sama persis yang dipakai agen,
dijalankan atas warehouse yang di-commit ke repo.

Kliennya sengaja dibuat dalam mode offline: panggilan jaringan apa pun akan
melempar `TransportUnavailable`, bukan diam-diam menyentuh internet. Jadi
"nol jaringan" di sini terbukti, bukan diklaim.

Warehouse yang dipakai, berurutan:
  1. data/warehouse/     — tarikan Sectors asli, kalau sudah di-commit
  2. fixtures/warehouse-mini/ — fixture sintetis, supaya demo tetap jalan
                                sebelum backfill pertama selesai

    make demo
    python -m core.probes.demo --symbol FIXC --evidence
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from core.console import setup_console
from core.ingest.warehouse import Warehouse
from core.probes.base import Context
from core.probes.registry import PROBES, baseline_credits
from core.sectors.client import CreditAwareClient
from core.sectors.ledger import CreditLedger

ROOT = Path(__file__).resolve().parents[2]
ASLI = ROOT / "data" / "warehouse"
MINI = ROOT / "fixtures" / "warehouse-mini"


def pilih_warehouse(pilihan: Path | None = None) -> tuple[Warehouse, str]:
    if pilihan:
        return Warehouse(pilihan), "ditentukan lewat --warehouse"
    if (ASLI / "daily_close.parquet").exists():
        return Warehouse(ASLI), "data Sectors asli yang di-commit"
    return Warehouse(MINI), "fixture sintetis (SELURUH ANGKA KARANGAN)"


def tanggal_acuan(wh: Warehouse) -> date | None:
    """as_of yang benar untuk warehouse ini.

    Bukan max(trade_date): fixture sintetis sengaja memuat baris SETELAH as_of
    sebagai umpan lookahead, dan memakai tanggal terbesar berarti demo berjalan
    di masa depan fixture-nya sendiri. Kalau ada meta.json, itu yang dipakai.
    """
    import json

    import pandas as pd

    meta = wh.path / "meta.json"
    if meta.exists():
        try:
            return date.fromisoformat(json.loads(meta.read_text(encoding="utf-8"))["as_of"])
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            pass
    if not wh.exists("daily_close"):
        return None
    df = wh.frame("daily_close")
    return None if df.empty else pd.to_datetime(df["trade_date"]).max().date()


def simbol_tersedia(wh: Warehouse, as_of: date) -> list[str]:
    df = wh.frame("daily_close", as_of=as_of)
    return sorted(df["symbol"].unique().tolist()) if not df.empty else []


def jalankan(wh: Warehouse, as_of: date, symbols: list[str],
             client: CreditAwareClient) -> dict[str, dict]:
    hasil: dict[str, dict] = {}
    for symbol in symbols:
        ctx = Context(as_of=as_of, warehouse=wh, client=client, budget_remaining=0)
        hasil[symbol] = {p.name: p.run(symbol, ctx) for p in PROBES.values()}
    return hasil


def tabel(hasil: dict[str, dict]) -> str:
    kode = [p.component for p in PROBES.values()]
    baris = [f"{'ticker':<8}" + "".join(f"{k:>8}" for k in kode) + f"{'kredit':>9}"]
    baris.append("-" * len(baris[0]))
    for symbol, probes in hasil.items():
        sel = []
        for p in PROBES.values():
            r = probes[p.name]
            sel.append(f"{r.sub_score:>8.1f}" if r.sub_score is not None else f"{'n/a':>8}")
        biaya = sum(r.credits_spent for r in probes.values())
        baris.append(f"{symbol:<8}" + "".join(sel) + f"{biaya:>9}")
    return "\n".join(baris)


def alasan_tak_tersedia(hasil: dict[str, dict]) -> str:
    keluar = []
    for symbol, probes in hasil.items():
        for name, r in probes.items():
            if r.sub_score is None:
                keluar.append(f"  {symbol}/{name}: {r.unavailable_reason}")
    if not keluar:
        return ""
    return ("\nKomponen yang tidak tersedia — dengan alasannya, bukan nol diam-diam:\n"
            + "\n".join(keluar))


def buku_bukti(symbol: str, probes: dict) -> str:
    baris = [f"\nBuku bukti {symbol} — tiap angka bisa ditelusuri balik ke sumbernya [T12]:"]
    for name, r in probes.items():
        if r.sub_score is None:
            continue
        baris.append(f"\n  {name} ({r.sub_score})")
        for e in r.evidence:
            baris.append(f"    {e.id:<24} {e.display:>14}   {e.label}")
            baris.append(f"    {'':<24} {'':>14}   <- {e.source_endpoint} "
                         f"[{e.source_transport}] per {e.as_of:%d-%m-%Y}")
    return "\n".join(baris)


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Demo probe PANTAU — nol jaringan, nol kredit")
    ap.add_argument("--warehouse", type=Path, default=None)
    ap.add_argument("--as-of", type=date.fromisoformat, default=None)
    ap.add_argument("--symbol", default=None, help="tampilkan buku bukti satu ticker")
    ap.add_argument("--evidence", action="store_true", help="buku bukti untuk semua ticker")
    args = ap.parse_args(argv)

    wh, asal = pilih_warehouse(args.warehouse)
    as_of = args.as_of or tanggal_acuan(wh)
    if as_of is None:
        print(f"warehouse {wh.path} kosong. Jalankan: make warehouse-mini")
        return 1

    symbols = [args.symbol] if args.symbol else simbol_tersedia(wh, as_of)
    if not symbols:
        print(f"tidak ada ticker di warehouse pada {as_of}")
        return 1

    print("PANTAU — demo probe")
    print(f"warehouse : {wh.path.relative_to(ROOT)}  ({asal})")
    print(f"as_of     : {as_of}")
    print("jaringan  : DIMATIKAN — klien mode offline, panggilan apa pun akan melempar\n")

    # Ledger sementara: demo tidak boleh menyentuh posisi kredit sungguhan.
    ledger = CreditLedger(ROOT / "data" / "cache" / "_demo_ledger.jsonl")
    with CreditAwareClient(offline=True, ledger=ledger, phase="dev") as client:
        hasil = jalankan(wh, as_of, symbols, client)

    print(tabel(hasil))
    print("\nBCI broker · VAS volume · PFD harga-vs-fundamental · FFS free float · "
          "FRD arus asing · SSS struktural")
    print(f"Investigasi menyeluruh dianggarkan {baseline_credits()} kredit; "
          f"demo ini menghabiskan 0 karena seluruhnya dilayani warehouse yang di-commit.")

    print(alasan_tak_tersedia(hasil))

    if args.evidence or args.symbol:
        for symbol in symbols:
            print(buku_bukti(symbol, hasil[symbol]))

    print("\nSkor komponen di atas BUKAN Skor PANTAU. Pembobotan, band, dan narasi "
          "ada di lajur Hamzah (core/scoring, core/agent); halaman investigasi di "
          "lajur Nadhilla (web/).")
    print("\nPANTAU adalah alat informasi dan analisis, bukan saran investasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
