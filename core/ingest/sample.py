"""Pilih sampel kalibrasi: himpunan positif + kontrol tersamakan. Nol kredit.

Anggaran memaksa sampel kecil, dan itu harus dinyatakan terbuka, bukan disamarkan.
Himpunan positif nyata berisi **228 emiten**; menariknya lengkap dengan Tier-2
berharga ~2.900 kredit sementara jatah tim 1.000. Jadi yang dikalibrasi adalah
sampel, dan `ARCHITECTURE.md` §6 memang sudah mewajibkan keterbatasan ini ditulis
di halaman Metodologi.

**Cara kontrol dipilih.** `ARCHITECTURE.md` §6 meminta pencocokan berdasarkan
kapitalisasi & subsektor. Keduanya butuh `company_profile`, yang baru terisi
SETELAH Tier-2 ditarik — ayam dan telur. Yang tersedia gratis untuk seluruh pasar
adalah **free float** (961 emiten, 1 kredit), jadi kontrol dicocokkan pada free
float dan disyaratkan tidak pernah disuspend.

Itu pencocokan yang lebih lemah, dan lemahnya ke arah yang bisa diperiksa: free
float adalah salah satu dari enam komponen, jadi mencocokkannya justru
menghilangkan pembeda yang paling gampang dipelajari model. Kapitalisasi dan
subsektor tetap ikut ditarik lewat `fetch-company-report` di Tier-2, supaya
Hamzah bisa MEMERIKSA seberapa timpang sampelnya setelah data ada — dan
membuang pasangan yang tidak layak.

    python -m core.ingest.sample --size 8
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from core.console import setup_console
from core.ingest.backfill import ALASAN_POSITIF
from core.ingest.warehouse import Warehouse

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "backfill" / "sample.json"

TOLERANSI_FLOAT = 0.05
"""Selisih free float maksimum antara positif dan kontrolnya."""


def positives_ranked(wh: Warehouse, as_of: date) -> pd.DataFrame:
    """Emiten dengan suspensi pergerakan-tidak-wajar, diurut dari yang paling
    berguna untuk kalibrasi: peristiwa terbaru dan paling sedikit berulang.

    Peristiwa terbaru dipilih karena riwayat harganya paling mungkin masih
    tersedia lewat fetch-daily-transaction; suspensi 2024 menuntut jendela
    tarikan yang jauh lebih panjang dan lebih mahal.
    """
    susp = wh.frame("suspensions", as_of=as_of)
    if susp.empty:
        return pd.DataFrame()

    susp = susp.copy()
    susp["alasan"] = susp["reason"].astype(str).str.lower()
    susp["positif"] = susp["alasan"].apply(
        lambda a: any(k in a for k in ALASAN_POSITIF)
    )
    pos = susp[susp["positif"]]
    if pos.empty:
        return pd.DataFrame()

    ringkas = (pos.groupby("symbol")
                  .agg(peristiwa=("start_date", "size"),
                       terakhir=("start_date", "max"))
                  .reset_index()
                  .sort_values("terakhir", ascending=False))
    return ringkas


def pick(wh: Warehouse, as_of: date, size: int = 8) -> dict:
    """Sampel seimbang: `size` positif + `size` kontrol tersamakan free float."""
    pos = positives_ranked(wh, as_of)
    if pos.empty:
        return {"positives": [], "controls": [], "catatan": "tidak ada suspensi positif"}

    ff = wh.frame("free_float", as_of=as_of)
    float_map = dict(zip(ff["symbol"], ff["free_float_pct"], strict=False)) if not ff.empty else {}
    pernah_suspend = set(wh.frame("suspensions", as_of=as_of)["symbol"])

    terpilih, kontrol, dipakai = [], [], set(pernah_suspend)
    for _, row in pos.iterrows():
        if len(terpilih) >= size:
            break
        symbol = row["symbol"]
        ff_pos = float_map.get(symbol)
        if ff_pos is None:
            continue  # tanpa free float, tidak ada dasar pencocokan

        pasangan = _match(symbol, ff_pos, float_map, dipakai)
        if pasangan is None:
            continue  # positif tanpa kontrol layak tidak dipakai — sampel wajib seimbang

        terpilih.append({
            "symbol": symbol,
            "peristiwa": int(row["peristiwa"]),
            "suspensi_terakhir": str(pd.to_datetime(row["terakhir"]).date()),
            "free_float": round(float(ff_pos), 4),
        })
        kontrol.append({
            "symbol": pasangan,
            "dipasangkan_dengan": symbol,
            "free_float": round(float(float_map[pasangan]), 4),
            "selisih_float": round(abs(float_map[pasangan] - ff_pos), 4),
        })
        dipakai.add(pasangan)

    return {
        "as_of": as_of.isoformat(),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "metode_kontrol": "free float terdekat, belum pernah disuspend",
        "keterbatasan": (
            "Pencocokan kapitalisasi & subsektor yang diminta ARCHITECTURE §6 belum "
            "bisa dilakukan: company_profile baru terisi setelah Tier-2 ditarik. "
            "Periksa ulang keseimbangan sampel setelah data ada, dan buang pasangan "
            "yang subsektornya jauh berbeda."
        ),
        "positif_tersedia": int(len(pos)),
        "positif_dipakai": len(terpilih),
        "positives": terpilih,
        "controls": kontrol,
        "symbols": [p["symbol"] for p in terpilih] + [c["symbol"] for c in kontrol],
    }


def _match(symbol: str, ff_pos: float, float_map: dict, dipakai: set) -> str | None:
    kandidat = [
        (abs(ff - ff_pos), s) for s, ff in float_map.items()
        if s not in dipakai and s != symbol and abs(ff - ff_pos) <= TOLERANSI_FLOAT
    ]
    return min(kandidat)[1] if kandidat else None


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Pilih sampel kalibrasi (nol kredit)")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--size", type=int, default=8, help="jumlah positif (kontrol sama banyak)")
    ap.add_argument("--warehouse", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    hasil = pick(Warehouse(args.warehouse), args.as_of, args.size)
    if not hasil.get("positives"):
        print("sampel kosong — jalankan backfill tahap 2 lebih dulu")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(hasil, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    print(f"SAMPEL KALIBRASI — {hasil['positif_dipakai']} positif + "
          f"{len(hasil['controls'])} kontrol (dari {hasil['positif_tersedia']} positif tersedia)")
    print(f"{'positif':<8} {'float':>7}  {'suspensi':<12} {'kontrol':<8} {'float':>7} {'selisih':>8}")
    for p, k in zip(hasil["positives"], hasil["controls"], strict=True):
        print(f"{p['symbol']:<8} {p['free_float'] * 100:>6.1f}%  {p['suspensi_terakhir']:<12} "
              f"{k['symbol']:<8} {k['free_float'] * 100:>6.1f}% {k['selisih_float'] * 100:>7.1f}%")
    print(f"\n-> {args.out}")
    print(f"\nJalankan Tier-2 untuk sampel ini:\n"
          f"  python -m core.ingest.backfill --stage 1 --as-of {args.as_of} "
          f"--symbols {' '.join(hasil['symbols'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
