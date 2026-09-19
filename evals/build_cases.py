"""Susun alam semesta eval dari warehouse yang di-commit. Nol jaringan.

Ticker tidak pernah ditulis tangan: emiten yang tidak punya riwayat harga cukup
akan membuat setiap lengan menghasilkan "n/a" dan evalnya membandingkan kekosongan.

    python3 evals/build_cases.py --tulis
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases.yaml"
MIN_SESI = 40

KUERI = """
with harga as (
    select symbol, count(*) n
    from read_parquet('{wh}/daily_transaction.parquet') group by 1
),
broker as (select distinct symbol from read_parquet('{wh}/broker_summary.parquet')),
susp   as (select distinct symbol from read_parquet('{wh}/suspensions.parquet'))
select h.symbol, h.n,
       (b.symbol is not null) as punya_broker,
       (s.symbol is not null) as pernah_suspend
from harga h
left join broker b using(symbol)
left join susp   s using(symbol)
where h.n >= {min_sesi}
order by pernah_suspend desc, punya_broker desc, h.n desc, h.symbol
"""


def kumpulkan(warehouse: Path | None = None) -> list[dict]:
    import duckdb

    wh = (warehouse or ROOT / "data" / "warehouse").as_posix()
    rows = duckdb.sql(KUERI.format(wh=wh, min_sesi=MIN_SESI)).fetchall()
    return [
        {"symbol": r[0], "sesi": int(r[1]),
         "punya_broker": bool(r[2]), "pernah_suspend": bool(r[3])}
        for r in rows
    ]


def render(kasus: list[dict]) -> str:
    n_susp = sum(1 for k in kasus if k["pernah_suspend"])
    n_brok = sum(1 for k in kasus if k["punya_broker"])
    baris = [
        "# Alam semesta eval agen — DIBANGKITKAN, jangan disunting tangan.",
        "#   python3 evals/build_cases.py --tulis",
        "#",
        f"# {len(kasus)} emiten dengan >= {MIN_SESI} sesi harga di warehouse yang di-commit.",
        f"# {n_susp} pernah disuspend, {n_brok} punya data broker.",
        "#",
        "# Jumlah ini di bawah sasaran 30-50 di TASK_HAMZAH.md, dan itu bukan kelalaian:",
        "# warehouse memang baru memuat sebanyak ini. Angka 2 dilaporkan dengan ukuran",
        "# sampel yang dinyatakan terbuka, bukan dengan alam semesta yang dikarang.",
        "kasus:",
    ]
    for k in kasus:
        baris.append(
            f"  - symbol: {k['symbol']}\n"
            f"    sesi: {k['sesi']}\n"
            f"    punya_broker: {str(k['punya_broker']).lower()}\n"
            f"    pernah_suspend: {str(k['pernah_suspend']).lower()}"
        )
    return "\n".join(baris) + "\n"


def muat(path: Path | None = None) -> list[dict]:
    """Baca cases.yaml tanpa dependensi PyYAML — bentuknya kita yang tentukan."""
    teks = (path or CASES).read_text(encoding="utf-8")
    kasus, saat_ini = [], None
    for baris in teks.splitlines():
        s = baris.strip()
        if s.startswith("#") or not s or s == "kasus:":
            continue
        if s.startswith("- symbol:"):
            if saat_ini:
                kasus.append(saat_ini)
            saat_ini = {"symbol": s.split(":", 1)[1].strip()}
        elif saat_ini and ":" in s:
            k, v = (x.strip() for x in s.split(":", 1))
            saat_ini[k] = int(v) if v.isdigit() else v == "true"
    if saat_ini:
        kasus.append(saat_ini)
    return kasus


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tulis", action="store_true")
    args = ap.parse_args(argv)

    kasus = kumpulkan()
    isi = render(kasus)
    if args.tulis:
        CASES.write_text(isi, encoding="utf-8")
        print(f"tulis {CASES.relative_to(ROOT)} — {len(kasus)} kasus")
    else:
        print(isi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
