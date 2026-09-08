"""Hitung sub-skor point-in-time di T-n sebelum peristiwa. Nol kredit. Melco → Hamzah.

Ini serah-terima, bukan kalibrasi. Yang dikerjakan di sini cuma menjalankan enam
probe pada tanggal-tanggal yang diminta `ARCHITECTURE.md` §6 (T-1, T-3, T-5,
T-10 hari bursa sebelum suspensi) dan menuliskan hasilnya apa adanya. Pencarian
bobot, split waktu, dan Precision@20 ada di lajur Hamzah.

**Kenapa harus lewat berkas ini dan bukan dihitung ulang di notebook.** Point-in-time
ditegakkan `Warehouse.connect(as_of)`, bukan oleh kedisiplinan penulis query.
Menjalankan probe lewat jalur lain berarti melewati pagar itu, dan lookahead
masuk tanpa ada yang sadar.

    python -m core.probes.pit_eval --as-of 2026-09-07
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from core.console import setup_console
from core.ingest.warehouse import Warehouse, trading_days
from core.probes.base import Context
from core.probes.registry import PROBES

ROOT = Path(__file__).resolve().parents[2]
SAMPEL = ROOT / "runs" / "backfill" / "sample.json"
OUT = ROOT / "runs" / "backfill" / "pit-scores.json"

LAGS = (1, 3, 5, 10)
"""Hari bursa sebelum peristiwa. ARCHITECTURE §6 langkah 3."""


def sesi_sebelum(wh: Warehouse, peristiwa: date, lag: int) -> date | None:
    """Tanggal bursa ke-`lag` sebelum peristiwa, dari kalender yang benar-benar ada."""
    hari = trading_days(wh, peristiwa - timedelta(days=1), lag)
    return hari[0] if len(hari) >= lag else None


def skor(wh: Warehouse, symbol: str, as_of: date) -> dict[str, float | None]:
    ctx = Context(as_of=as_of, warehouse=wh, client=None, budget_remaining=0)
    return {p.component: p.run(symbol, ctx).sub_score for p in PROBES.values()}


def evaluate(wh: Warehouse, sampel: dict) -> dict:
    baris = []
    pasangan = zip(sampel["positives"], sampel["controls"], strict=True)
    for pos, ktl in pasangan:
        peristiwa = date.fromisoformat(pos["suspensi_terakhir"])
        for lag in LAGS:
            hari = sesi_sebelum(wh, peristiwa, lag)
            if hari is None:
                continue
            for symbol, label in ((pos["symbol"], 1), (ktl["symbol"], 0)):
                baris.append({
                    "symbol": symbol, "label": label, "lag": lag,
                    "event_date": peristiwa.isoformat(), "as_of": hari.isoformat(),
                    "scores": skor(wh, symbol, hari),
                })
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "metode": "enam probe dijalankan lewat Warehouse.connect(as_of) — point-in-time "
                  "ditegakkan view, bukan query",
        "lags": list(LAGS),
        "peringatan": [
            "SSS bocor label: skornya memuat riwayat suspensi, dan label positif "
            "DIDEFINISIKAN dari suspensi. Keluarkan SSS, atau buang komponen "
            "suspensinya, sebelum mencari bobot — kalau tidak model cuma menghafal "
            "labelnya.",
            "BCI dan FFS sering None di T-n: broker summary yang kami tarik adalah "
            "agregat per akhir periode dan free float tidak membawa tanggal berlaku, "
            "jadi keduanya bertanggal tanggal tarikan dan tersaring keluar di masa "
            "lampau. Itu perilaku point-in-time yang BENAR, bukan bug — tapi artinya "
            "kedua komponen belum bisa dikalibrasi tanpa tarikan tambahan per tanggal.",
            "Sampel kecil (8 positif + 8 kontrol) karena anggaran kredit. Himpunan "
            "positif sesungguhnya 228 emiten.",
        ],
        "rows": baris,
    }


def ringkas(hasil: dict) -> str:
    kode = [p.component for p in PROBES.values()]
    lines = [f"{'lag':<5}{'kelas':<9}" + "".join(f"{k:>7}" for k in kode) + f"{'n':>5}"]
    lines.append("-" * len(lines[0]))
    for lag in hasil["lags"]:
        for label, nama in ((1, "positif"), (0, "kontrol")):
            grup = [r for r in hasil["rows"] if r["lag"] == lag and r["label"] == label]
            if not grup:
                continue
            sel = []
            for k in kode:
                nilai = [r["scores"][k] for r in grup if r["scores"].get(k) is not None]
                sel.append(f"{sum(nilai) / len(nilai):>7.1f}" if nilai else f"{'n/a':>7}")
            lines.append(f"T-{lag:<3} {nama:<9}" + "".join(sel) + f"{len(grup):>5}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Sub-skor point-in-time untuk kalibrasi")
    ap.add_argument("--sample", type=Path, default=SAMPEL)
    ap.add_argument("--warehouse", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    if not args.sample.exists():
        print(f"sampel tidak ada: {args.sample}. Jalankan: python -m core.ingest.sample")
        return 1

    sampel = json.loads(args.sample.read_text(encoding="utf-8"))
    hasil = evaluate(Warehouse(args.warehouse), sampel)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(hasil, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    print("SUB-SKOR POINT-IN-TIME — rata-rata per kelas\n")
    print(ringkas(hasil))
    print("\nPeringatan yang WAJIB dibaca sebelum mencari bobot:")
    for w in hasil["peringatan"]:
        print(f"  - {w}")
    print(f"\n{len(hasil['rows'])} baris -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
