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
    python tools/investigate_watchlist.py --requests --symbols BBCA      # + permintaan [T3]
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
from core.agent.runner import investigate_symbol, sinyal_watchlist  # noqa: E402
from core.agent.transcript import path_for, save  # noqa: E402
from core.console import setup_console  # noqa: E402
from core.ingest.warehouse import Warehouse, trading_days  # noqa: E402
from core.sectors.client import CreditAwareClient  # noqa: E402
from core.sectors.errors import BudgetExceeded  # noqa: E402
from core.sectors.ledger import CreditLedger  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402
from tools import permintaan as jalur  # noqa: E402

log = get_logger(__name__)

DEFAULT_TOP = 3
"""Berapa kandidat teratas diselidiki per hari. Sengaja kecil: tiap investigasi
bisa menembak sampai 25 kredit, dan operasi harian dipagari 250. Top-3 menjaga
±10 kredit/hari khas, sesuai anggaran ARCHITECTURE §7."""


JEDA_HARI_BURSA = 2
"""Berapa hari bursa sebuah kesimpulan berkeyakinan tinggi masih dianggap berlaku."""

JEDA_KEYAKINAN = 0.6
"""Di bawah ini kesimpulan kemarin terlalu tipis untuk dijadikan alasan melewati."""

JEDA_DELTA_SELEKSI = 0.05
"""Perubahan skor seleksi Tahap 1 yang dianggap berarti. Di bawah ini, tidak ada
yang baru untuk dilihat — yang membuat emiten ini menarik kemarin masih sama."""


def read_candidates(as_of: date, runs_root: Path) -> list[dict]:
    path = runs_root / as_of.isoformat() / "watchlist.json"
    if not path.exists():
        raise FileNotFoundError(
            f"watchlist {path} tidak ada — jalankan Tahap 1 (sapuan Tier-1) dulu"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    cand = data.get("candidates") or []
    return sorted(cand, key=lambda c: c.get("score", 0), reverse=True)


def _alasan_jeda(mem: Memory, symbol: str, as_of: date, entri: dict,
                 wh: Warehouse, runs_root: Path) -> str | None:
    """Alasan melewati kandidat ini, atau None kalau layak diselidiki.

    Tiga syarat harus terpenuhi sekaligus — baru, yakin, dan tidak bergerak.
    Satu saja meleset berarti ada sesuatu yang berubah, dan investigasi jalan.
    """
    ingat = mem.recall(symbol, before=as_of)
    if ingat is None:
        return None
    if ingat.confidence < JEDA_KEYAKINAN:
        return None
    try:
        sesi = trading_days(wh, as_of, JEDA_HARI_BURSA + 1)
    except Exception:  # noqa: BLE001 — kalender tidak terbaca → jangan melewati
        return None
    if not sesi or ingat.as_of < sesi[0]:
        return None

    lama = _skor_seleksi_tersimpan(symbol, ingat.as_of, runs_root)
    baru = entri.get("score")
    if lama is None or baru is None:
        return None
    if abs(float(baru) - float(lama)) >= JEDA_DELTA_SELEKSI:
        return None

    return (f"diselidiki {ingat.as_of.isoformat()} (keyakinan "
            f"{ingat.confidence:.0%}), skor seleksi bergerak "
            f"{abs(float(baru) - float(lama)):.3f} < {JEDA_DELTA_SELEKSI}")


def _skor_seleksi_tersimpan(symbol: str, hari: date, runs_root: Path) -> float | None:
    """Skor seleksi Tahap 1 untuk emiten ini pada hari investigasi sebelumnya."""
    path = runs_root / hari.isoformat() / "watchlist.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    for c in data.get("candidates") or []:
        if c.get("symbol") == symbol:
            skor = c.get("score")
            return float(skor) if skor is not None else None
    return None


def run(as_of: date, *, top: int = DEFAULT_TOP, offline: bool = False,
        runs_root: Path | None = None, warehouse: Warehouse | None = None,
        ledger: CreditLedger | None = None, client: object | None = None,
        memory: Memory | None = None, permintaan: list[str] | None = None) -> dict:
    """`permintaan`: kode emiten yang diminta orang (sudah divalidasi
    tools/permintaan.py). Diselidiki LEBIH DULU dan tidak kena jeda seleksi —
    seseorang memintanya secara eksplisit. [AUDIT T3]"""
    runs_root = runs_root or (ROOT / "runs")
    inv_root = runs_root / "investigations"
    wh = warehouse or Warehouse()
    # Memori per-ticker: investigasi ulang emiten yang sama menghasilkan delta,
    # bukan mulai dari nol. Salah satu dari empat perilaku agentik Track 1.
    mem = memory if memory is not None else Memory()

    candidates = read_candidates(as_of, runs_root)
    diminta = list(dict.fromkeys(permintaan or []))
    dipilih = [c["symbol"] for c in candidates[:top]]
    if not dipilih and not diminta:
        log.info("watchlist %s kosong — tidak ada yang diselidiki", as_of)
        return {"as_of": as_of.isoformat(), "diselidiki": [], "dilewati": [],
                "gagal": [], "kredit": 0, "status": {}}

    # Satu klien berbagi untuk seluruh batch: pagu fase memotong lintas investigasi.
    if client is None and not offline:
        client = CreditAwareClient(phase="daily", ledger=ledger,
                                   run_id=f"investigate-{as_of.isoformat()}")

    diselidiki: list[dict] = []
    dilewati: list[str] = []
    gagal: list[str] = []
    # Nasib tiap emiten yang disentuh batch ini — dibaca balik oleh jalur
    # permintaan untuk menutup issue yang terpenuhi.
    status: dict[str, str] = {}

    per_simbol = {c["symbol"]: c for c in candidates}
    cadangan = [c["symbol"] for c in candidates[top:] if c["symbol"] not in diminta]

    antrean = diminta + [s for s in dipilih if s not in diminta]
    while antrean:
        symbol = antrean.pop(0)
        if symbol in status:
            continue
        entri = per_simbol.get(symbol, {})
        tujuan = path_for(symbol, as_of, inv_root)
        if tujuan.exists():
            log.info("%s sudah diselidiki untuk %s — dilewati", symbol, as_of)
            dilewati.append(symbol)
            status[symbol] = "sudah_ada"
            continue

        # Jeda seleksi: memori dipakai untuk MEMILIH, bukan cuma merencanakan.
        # Tanpa ini top-3 yang sama diselidiki sembilan hari berturut-turut dan
        # kredit `daily` terbakar untuk delta nol. [B9] Permintaan eksplisit
        # tidak kena jeda.
        if symbol not in diminta and (
                alasan := _alasan_jeda(mem, symbol, as_of, entri, wh, runs_root)):
            log.info("%s dilewati: %s", symbol, alasan)
            dilewati.append(f"{symbol}: {alasan}")
            status[symbol] = "jeda"
            if cadangan:
                pengganti = cadangan.pop(0)
                log.info("%s naik menggantikan %s", pengganti, symbol)
                antrean.append(pengganti)
            continue

        try:
            # persist=False: kita simpan sendiri ke inv_root supaya jalur output
            # satu sumber (dan bisa diarahkan ke tmp saat tes). Memori tetap
            # diperbarui di bawah, jadi perilaku delta tidak hilang.
            t = investigate_symbol(symbol, as_of=as_of, offline=offline,
                                   warehouse=wh, memory=mem,
                                   client=None if offline else client, persist=False,
                                   signals=sinyal_watchlist(entri))
            path = save(t, root=inv_root)
            mem.remember(t, path)
        except BudgetExceeded as exc:
            # Pagu fase habis: sisanya dilewati, bukan dipaksa. Investigasi yang
            # sudah tersimpan tetap sah.
            log.warning("pagu kredit habis di %s (%s) — sisa kandidat dilewati",
                        symbol, exc)
            gagal.append(f"{symbol}: pagu habis")
            for s in [symbol, *antrean]:
                status.setdefault(s, "pagu")
            break
        except Exception as exc:  # noqa: BLE001 — satu gagal tak menjatuhkan batch
            log.exception("investigasi %s gagal", symbol)
            gagal.append(f"{symbol}: {type(exc).__name__}: {exc}"[:120])
            status[symbol] = "gagal"
            continue

        status[symbol] = "diselidiki"
        diselidiki.append({
            "symbol": symbol, "skor": t.pantau_score, "band": t.band,
            "kredit": t.credits_total, "langkah": len(t.steps),
            "narasi_dari": t.narrative_source,
        })
        log.info("%s → skor %d (%s), %d kredit, %d langkah",
                 symbol, t.pantau_score, t.band, t.credits_total, len(t.steps))

    kredit = sum(d["kredit"] for d in diselidiki)
    return {"as_of": as_of.isoformat(), "diselidiki": diselidiki,
            "dilewati": dilewati, "gagal": gagal, "kredit": kredit, "status": status}


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Cron Tahap 2 — selidiki top-N watchlist")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--top", type=int, default=DEFAULT_TOP)
    ap.add_argument("--offline", action="store_true",
                    help="FakeLLM, nol kunci — untuk uji mekanisme tanpa belanja")
    ap.add_argument("--runs", type=Path, default=None)
    ap.add_argument("--requests", action="store_true",
                    help=f"baca issue terbuka berlabel '{jalur.LABEL}' lewat gh [AUDIT T3]")
    ap.add_argument("--symbols", default="",
                    help="kode emiten dipisah koma, diselidiki lebih dulu (workflow_dispatch)")
    args = ap.parse_args(argv)
    runs_root = args.runs or (ROOT / "runs")
    wh = Warehouse()

    # Jalur permintaan tidak boleh menjatuhkan Tahap 2: issue yang tak terbaca
    # berarti malam ini tanpa permintaan, bukan malam ini tanpa investigasi.
    daftar: list[dict] = []
    if args.requests or args.symbols:
        issues: list[dict] = []
        if args.requests:
            try:
                issues = jalur.baca_issue()
            except Exception as exc:  # noqa: BLE001
                print(f"⚠ issue permintaan tidak terbaca ({type(exc).__name__}) — "
                      "dilanjutkan tanpa permintaan")
        daftar = jalur.siapkan(issues, args.symbols.split(","), jalur.kode_sah(wh))

    try:
        hasil = run(args.as_of, top=args.top, offline=args.offline, runs_root=runs_root,
                    warehouse=wh, permintaan=jalur.diterima(daftar))
    except FileNotFoundError as exc:
        print(f"⚠ {exc}")
        return 1

    if daftar:
        daftar = jalur.terapkan_hasil(daftar, hasil["status"])
        jalur.simpan(daftar, args.as_of, runs_root)
        print(f"\nPERMINTAAN — {len(daftar)} masuk")
        for p in daftar:
            asal = f"#{p['issue']}" if p.get("issue") else "dispatch"
            print(f"  {asal:<9} {p['symbol'] or '—':<6} {p['status']}")

    print(f"\nTAHAP 2 — investigasi {args.as_of}"
          f"{' (offline)' if args.offline else ''}")
    for d in hasil["diselidiki"]:
        print(f"  ✓ {d['symbol']:<6} skor {d['skor']:>3} ({d['band']:<14}) "
              f"{d['kredit']:>2} kredit · {d['langkah']} langkah · {d['narasi_dari']}")
    for s in hasil["dilewati"]:
        # Jeda seleksi membawa alasannya sendiri ("SYM: alasan"); sisanya memang
        # transkrip yang sudah ada — jangan dicetak seolah sama.
        print(f"  · {s}" if ":" in s else f"  · {s:<6} sudah ada, dilewati")
    for g in hasil["gagal"]:
        print(f"  ✗ {g}")
    print(f"\n{len(hasil['diselidiki'])} transkrip baru, {hasil['kredit']} kredit terpakai")
    # Batch dianggap sukses selama tidak SEMUA kandidat gagal — sebagian transkrip
    # tetap berharga, dan cron tidak boleh merah cuma karena satu LLM timeout.
    return 0 if (hasil["diselidiki"] or hasil["dilewati"] or not hasil["gagal"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
