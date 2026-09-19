"""Cron Tahap 2 — panggil agen untuk top-N kandidat watchlist, commit transkrip.

Tahap 1 (`core.ingest.tier1_market`) menghasilkan `runs/<as_of>/watchlist.json`
berisi kandidat terurut skor. Tahap 2 ini mengambil beberapa teratas dan
menjalankan agen sungguhan atas masing-masing, menyimpan transkrip ke
`runs/investigations/<SYM>-<as_of>.json`. Itulah bukti operasi otonom yang bukan
sekadar sapuan data, melainkan **penyelidikan** — inti Track 1. [T5]

Tiga hal yang dijaga berkas ini, karena ini berjalan tanpa pengawasan di cron:

1. **Pagu kredit ditegakkan, bukan diharapkan.** Semua investigasi berbagi satu
   `CreditAwareClient` fase `daily`, jadi pagu fase (250) memotong seluruh batch,
   bukan cuma satu investigasi. Begitu pagu tertembus, sisa kandidat dilewati —
   bukan crash. Agen sendiri sudah dipagari 25 kredit per investigasi [AD-6];
   ini pagar kedua di atasnya.
2. **Satu emiten gagal tidak menjatuhkan batch.** LLM ngambek, data kurang,
   apa pun — dicatat, lanjut ke kandidat berikutnya. Transkrip yang berhasil
   tetap tersimpan.
3. **Idempoten.** Kandidat yang transkripnya sudah ada untuk `as_of` ini
   dilewati. Cron yang diulang di hari yang sama tidak membayar dua kali dan
   tidak menimpa transkrip yang sudah baik.

    python tools/investigate_watchlist.py --as-of 2026-09-11 --top 3
    python tools/investigate_watchlist.py --as-of 2026-09-11 --offline   # FakeLLM
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.agent.memory import Memory  # noqa: E402
from core.agent.runner import investigate_symbol  # noqa: E402
from core.agent.transcript import path_for, save  # noqa: E402
from core.console import setup_console  # noqa: E402
from core.ingest.warehouse import Warehouse  # noqa: E402
from core.sectors.client import CreditAwareClient  # noqa: E402
from core.sectors.errors import BudgetExceeded  # noqa: E402
from core.sectors.ledger import CreditLedger  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)

DEFAULT_TOP = 3
"""Berapa kandidat teratas diselidiki per hari. Sengaja kecil: tiap investigasi
bisa menembak sampai 25 kredit, dan operasi harian dipagari 250. Top-3 menjaga
±10 kredit/hari khas, sesuai anggaran ARCHITECTURE §7."""


def read_candidates(as_of: date, runs_root: Path) -> list[dict]:
    path = runs_root / as_of.isoformat() / "watchlist.json"
    if not path.exists():
        raise FileNotFoundError(
            f"watchlist {path} tidak ada — jalankan Tahap 1 (sapuan Tier-1) dulu"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    cand = data.get("candidates") or []
    return sorted(cand, key=lambda c: c.get("score", 0), reverse=True)


def run(as_of: date, *, top: int = DEFAULT_TOP, offline: bool = False,
        runs_root: Path | None = None, warehouse: Warehouse | None = None,
        ledger: CreditLedger | None = None, client: object | None = None,
        memory: Memory | None = None) -> dict:
    runs_root = runs_root or (ROOT / "runs")
    inv_root = runs_root / "investigations"
    wh = warehouse or Warehouse()
    # Memori per-ticker: investigasi ulang emiten yang sama menghasilkan delta,
    # bukan mulai dari nol. Salah satu dari empat perilaku agentik Track 1.
    mem = memory if memory is not None else Memory()

    candidates = read_candidates(as_of, runs_root)
    dipilih = [c["symbol"] for c in candidates[:top]]
    if not dipilih:
        log.info("watchlist %s kosong — tidak ada yang diselidiki", as_of)
        return {"as_of": as_of.isoformat(), "diselidiki": [], "dilewati": [],
                "gagal": [], "kredit": 0}

    # Satu klien berbagi untuk seluruh batch: pagu fase memotong lintas investigasi.
    if client is None and not offline:
        client = CreditAwareClient(phase="daily", ledger=ledger,
                                   run_id=f"investigate-{as_of.isoformat()}")

    diselidiki: list[dict] = []
    dilewati: list[str] = []
    gagal: list[str] = []

    for symbol in dipilih:
        tujuan = path_for(symbol, as_of, inv_root)
        if tujuan.exists():
            log.info("%s sudah diselidiki untuk %s — dilewati", symbol, as_of)
            dilewati.append(symbol)
            continue

        try:
            # persist=False: kita simpan sendiri ke inv_root supaya jalur output
            # satu sumber (dan bisa diarahkan ke tmp saat tes). Memori tetap
            # diperbarui di bawah, jadi perilaku delta tidak hilang.
            t = investigate_symbol(symbol, as_of=as_of, offline=offline,
                                   warehouse=wh, memory=mem,
                                   client=None if offline else client, persist=False)
            path = save(t, root=inv_root)
            mem.remember(t, path)
        except BudgetExceeded as exc:
            # Pagu fase habis: sisanya dilewati, bukan dipaksa. Investigasi yang
            # sudah tersimpan tetap sah.
            log.warning("pagu kredit habis di %s (%s) — sisa kandidat dilewati",
                        symbol, exc)
            gagal.append(f"{symbol}: pagu habis")
            break
        except Exception as exc:  # noqa: BLE001 — satu gagal tak menjatuhkan batch
            log.exception("investigasi %s gagal", symbol)
            gagal.append(f"{symbol}: {type(exc).__name__}: {exc}"[:120])
            continue

        diselidiki.append({
            "symbol": symbol, "skor": t.pantau_score, "band": t.band,
            "kredit": t.credits_total, "langkah": len(t.steps),
            "narasi_dari": t.narrative_source,
        })
        log.info("%s → skor %d (%s), %d kredit, %d langkah",
                 symbol, t.pantau_score, t.band, t.credits_total, len(t.steps))

    kredit = sum(d["kredit"] for d in diselidiki)
    return {"as_of": as_of.isoformat(), "diselidiki": diselidiki,
            "dilewati": dilewati, "gagal": gagal, "kredit": kredit}


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Cron Tahap 2 — selidiki top-N watchlist")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--top", type=int, default=DEFAULT_TOP)
    ap.add_argument("--offline", action="store_true",
                    help="FakeLLM, nol kunci — untuk uji mekanisme tanpa belanja")
    ap.add_argument("--runs", type=Path, default=None)
    args = ap.parse_args(argv)

    try:
        hasil = run(args.as_of, top=args.top, offline=args.offline, runs_root=args.runs)
    except FileNotFoundError as exc:
        print(f"⚠ {exc}")
        return 1

    print(f"\nTAHAP 2 — investigasi {args.as_of}"
          f"{' (offline)' if args.offline else ''}")
    for d in hasil["diselidiki"]:
        print(f"  ✓ {d['symbol']:<6} skor {d['skor']:>3} ({d['band']:<14}) "
              f"{d['kredit']:>2} kredit · {d['langkah']} langkah · {d['narasi_dari']}")
    for s in hasil["dilewati"]:
        print(f"  · {s:<6} sudah ada, dilewati")
    for g in hasil["gagal"]:
        print(f"  ✗ {g}")
    print(f"\n{len(hasil['diselidiki'])} transkrip baru, {hasil['kredit']} kredit terpakai")
    # Batch dianggap sukses selama tidak SEMUA kandidat gagal — sebagian transkrip
    # tetap berharga, dan cron tidak boleh merah cuma karena satu LLM timeout.
    return 0 if (hasil["diselidiki"] or hasil["dilewati"] or not hasil["gagal"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
