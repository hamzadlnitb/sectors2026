"""Spike verifikasi endpoint F0 — butuh SECTORS_API_KEY. Anggaran maks 40 kredit.

Membuktikan enam probe benar-benar bisa dihitung dari data nyata. Kalau gagal,
desain diubah **sekarang**, bukan tanggal 20 September. Batas keputusan untuk
masalah bentuk data: 9 Sep. [TASK.md F0]

Yang dikerjakan sekali jalan:

1. panggil tiap endpoint kritis SATU KALI, simpan respons mentah ke spikes/raw/
2. catat biaya kredit **aktual** tiap endpoint ke spikes/observed.json
   → nilai ini menimpa asumsi di core/sectors/routing.py lewat load_observed()
3. tarik katalog tool MCP dan simpan ke spikes/mcp-tools.json
4. bangkitkan ulang docs/endpoint-costs.md dan docs/mcp-catalog.md

Biaya aktual **tidak bisa dibaca dari respons** — Sectors tidak mengirim ongkos
di body. Yang dilakukan skrip ini: membaca posisi ledger sebelum dan sesudah tiap
panggilan lewat header sisa kuota kalau ada, dan kalau tidak ada, mencatat biaya
asumsi sambil menandai `verified: false` supaya tidak ada yang mengira angkanya
terukur. Jujur soal apa yang belum diketahui lebih murah daripada menganggarkan
di atas tebakan. Kalau panitia mengonfirmasi ongkosnya di Slack, isi manual ke
spikes/observed.json — formatnya sengaja sederhana.

    make spike                       # semua endpoint
    python spikes/run_spike.py --only fetch-close fetch-suspensions
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.console import setup_console  # noqa: E402
from core.sectors import catalog, routing  # noqa: E402
from core.sectors.client import CreditAwareClient  # noqa: E402
from core.sectors.errors import SectorsError  # noqa: E402
from core.sectors.ledger import CreditLedger  # noqa: E402

RAW = ROOT / "spikes" / "raw"
OBSERVED = ROOT / "spikes" / "observed.json"
PAGU_SPIKE = 40

def _sampel(as_of: date) -> dict[str, dict]:
    """Params uji tiap endpoint kritis.

    BBCA dipakai karena besar dan likuid — kalau BBCA saja tidak punya data,
    yang rusak endpointnya, bukan emitennya. Ticker kecil akan membuat kedua
    kemungkinan itu tidak bisa dibedakan.
    """
    kemarin = (as_of - timedelta(days=1)).isoformat()
    bulan_lalu = (as_of - timedelta(days=30)).isoformat()
    dua_tahun = (as_of - timedelta(days=730)).isoformat()
    return {
        "fetch-close": {"date": kemarin},
        "fetch-most-traded-stocks": {"start": bulan_lalu, "end": kemarin, "n_stock": 10},
        "fetch-companies-top-changes": {"periods": "1d", "n_stock": 10},
        "fetch-suspensions": {"start": dua_tahun, "end": kemarin},
        "fetch-filings": {"start": bulan_lalu, "end": kemarin},
        "fetch-daily-transaction": {"symbol": "BBCA", "start": bulan_lalu, "end": kemarin},
        "fetch-broker-summary-top": {"symbol": "BBCA", "start": bulan_lalu, "end": kemarin},
        "fetch-foreign-flow": {"symbol": "BBCA", "start": bulan_lalu, "end": kemarin},
        "fetch-free-float": {"symbol": "BBCA"},
        "fetch-company-report": {"symbol": "BBCA"},
        "fetch-quarterly-financials": {"symbol": "BBCA", "n_quarters": 8},
        "fetch-corporate-actions": {"symbol": "BBCA", "start": dua_tahun, "end": kemarin},
    }


def jalankan(endpoints: list[str], as_of: date, ledger: CreditLedger) -> dict:
    sampel = _sampel(as_of)
    RAW.mkdir(parents=True, exist_ok=True)
    hasil: dict[str, dict] = {}

    with CreditAwareClient(phase="dev", ledger=ledger, run_id=f"spike-{as_of}") as client:
        for name in endpoints:
            params = sampel.get(name)
            if params is None:
                print(f"  lewati {name}: tidak ada sampel params")
                continue

            sebelum = ledger.spent("dev")
            try:
                resp = client.call(name, params, validate=False)
            except SectorsError as exc:
                # Kegagalan spike ADALAH hasil spike. Ini justru yang harus
                # ketahuan sekarang, bukan saat probe sudah ditulis.
                hasil[name] = {"ok": False, "error": str(exc)[:300],
                               "credit_cost": routing.cost_of(name), "verified": False}
                print(f"  GAGAL {name}: {str(exc)[:120]}")
                continue

            terpakai = ledger.spent("dev") - sebelum
            (RAW / f"{name}.json").write_text(
                json.dumps({"params": params, "payload": resp.payload},
                           ensure_ascii=False, indent=2, default=str)[:2_000_000],
                encoding="utf-8")

            bentuk = _bentuk(resp.payload)
            hasil[name] = {
                "ok": True,
                "credit_cost": terpakai or routing.cost_of(name),
                # Terukur hanya kalau ledger benar-benar bergerak (bukan cache hit).
                "verified": bool(terpakai) and not resp.cached,
                "transport": resp.transport,
                "cached": resp.cached,
                "shape": bentuk,
            }
            print(f"  {name:<30} {terpakai} kredit  {bentuk['kind']}, "
                  f"{bentuk['rows']} baris, kolom: {', '.join(bentuk['keys'][:8])}")
    return hasil


def _bentuk(payload) -> dict:
    """Ringkasan bentuk respons — inti spike. Ini yang menjawab pertanyaan
    'apakah fetch-broker-summary-top memberi cukup broker untuk HHI'."""
    from core.sectors.schemas import unwrap

    rows = unwrap(payload)
    return {
        "kind": type(payload).__name__,
        "rows": len(rows),
        "keys": sorted(rows[0].keys()) if rows else [],
    }


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Spike verifikasi endpoint F0")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--skip-mcp", action="store_true")
    args = ap.parse_args(argv)

    if not os.environ.get("SECTORS_API_KEY"):
        print("SECTORS_API_KEY tidak diset. Salin .env.example ke .env dan isi.")
        return 2

    ledger = CreditLedger()
    if ledger.remaining("dev") < PAGU_SPIKE:
        print(f"sisa pagu fase dev {ledger.remaining('dev')} kredit, "
              f"spike butuh sampai {PAGU_SPIKE} — dihentikan.")
        return 2

    endpoints = args.only or [e.name for e in routing.endpoints() if e.name in _sampel(args.as_of)]
    print(f"spike {len(endpoints)} endpoint, pagu dev tersisa {ledger.remaining('dev')} kredit\n")
    hasil = jalankan(endpoints, args.as_of, ledger)

    tools: list[dict] = []
    if not args.skip_mcp:
        try:
            tools = catalog.mcp_tools()
            catalog.save_dump(tools)
            print(f"\nkatalog MCP: {len(tools)} tool -> spikes/mcp-tools.json")
        except Exception as exc:  # noqa: BLE001 — MCP gagal tidak membatalkan spike REST
            print(f"\nkatalog MCP gagal ditarik: {str(exc)[:200]}")
            print("Ini masukan untuk keputusan 11 Sep (lanjut MCP atau REST-only), "
                  "bukan alasan menghentikan spike.")

    OBSERVED.write_text(json.dumps({
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "note": "Diisi make spike. credit_cost menimpa asumsi di core/sectors/routing.py. "
                "verified=false berarti angkanya masih asumsi.",
        "endpoints": hasil,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nbiaya terukur -> {OBSERVED.relative_to(ROOT)}")

    from tools.gen_docs import main as gen_docs

    gen_docs([])

    gagal = [n for n, r in hasil.items() if not r["ok"]]
    if gagal:
        print(f"\n{len(gagal)} endpoint gagal: {', '.join(gagal)}")
        print("Bawa ke TASK.md §Rencana Cadangan hari ini juga — batas keputusan 9 Sep.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
