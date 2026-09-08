"""Pulihkan payload berbayar yang tertahan di karantina skema. Nol kredit.

Ketika sebuah respons tidak lolos model pydantic, `CreditAwareClient` menaruhnya
di `data/cache/_rejected/` alih-alih di cache — supaya satu respons rusak tidak
terpakai selamanya. Tapi kreditnya **sudah terpotong**: API mengembalikan 200,
dan kita yang tidak bisa membacanya.

Kalau sebabnya parser kita (dan sejauh ini selalu begitu — bentuk respons yang
tidak kita duga), maka setelah parser diperbaiki payload itu **sudah benar dan
sudah dibayar**. Menariknya ulang berarti membayar dua kali untuk byte yang
sama.

Skrip ini menguji ulang tiap payload karantina dengan parser terkini. Yang lolos
dipindahkan ke cache permanen — jadi panggilan berikutnya gratis. Yang masih
gagal ditinggal di karantina beserta sebabnya.

    python tools/recover_rejected.py --dry-run
    python tools/recover_rejected.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.console import setup_console  # noqa: E402
from core.sectors.client import DEFAULT_CACHE, cache_key  # noqa: E402
from core.sectors.errors import SchemaError  # noqa: E402
from core.sectors.routing import transport_for  # noqa: E402
from core.sectors.schemas import parse_rows  # noqa: E402


def kandidat(cache_dir: Path) -> list[tuple[str, Path]]:
    tolak = cache_dir / "_rejected"
    if not tolak.exists():
        return []
    return sorted(
        (d.name, f) for d in tolak.iterdir() if d.is_dir() for f in d.glob("*.json")
    )


def pulihkan(cache_dir: Path, dry_run: bool = False) -> tuple[int, int, list[str]]:
    sembuh = gagal = 0
    sisa: list[str] = []

    for endpoint, path in kandidat(cache_dir):
        try:
            isi = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            sisa.append(f"{endpoint}: berkas karantina rusak ({exc})")
            gagal += 1
            continue

        params, payload = isi.get("params", {}), isi.get("payload")
        try:
            rows = parse_rows(endpoint, payload)
        except SchemaError as exc:
            sisa.append(f"{endpoint} {params}: {str(exc).splitlines()[0][:110]}")
            gagal += 1
            continue

        sembuh += 1
        print(f"  ✓ {endpoint:<28} {len(rows):>4} baris  {json.dumps(params)[:60]}")
        if dry_run:
            continue

        tujuan = cache_dir / endpoint / f"{cache_key(endpoint, params)}.json"
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        tujuan.write_text(json.dumps({
            "meta": {
                "endpoint": endpoint, "params": params,
                "transport": transport_for(endpoint),
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "recovered_from_quarantine": True,
            },
            "payload": payload,
        }, ensure_ascii=False, default=str), encoding="utf-8")
        path.unlink()

    return sembuh, gagal, sisa


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Pulihkan payload karantina (nol kredit)")
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    total = len(kandidat(args.cache))
    if not total:
        print("karantina kosong — tidak ada yang perlu dipulihkan")
        return 0

    print(f"{total} payload di karantina, diuji ulang dengan parser terkini:")
    sembuh, gagal, sisa = pulihkan(args.cache, args.dry_run)

    print(f"\n{sembuh} pulih, {gagal} masih gagal.")
    if sisa:
        print("\nMasih gagal:")
        for baris in sisa[:10]:
            print(f"  {baris}")
    if sembuh and args.dry_run:
        print("\n(dry-run: tidak ada yang dipindahkan. Jalankan tanpa --dry-run.)")
    elif sembuh:
        print("Payload pulih sudah masuk cache — panggilan berikutnya gratis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
