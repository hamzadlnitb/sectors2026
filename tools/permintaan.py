"""Jalur permintaan via GitHub Issue — orang meminta, cron yang menyelidiki. [AUDIT T3]

Nol backend: siapa pun membuka issue dari template `selidiki`, cron malam
berikutnya membacanya, menyelidiki emiten itu SEBELUM top-N watchlist, lalu
menutup issue dengan tautan transkrip. Tetap otonom (tidak ada manusia di
dalam lingkaran), dan setiap permintaan tercatat di `runs/<tanggal>/permintaan.json`.

Tiga hal yang dijaga, karena repo ini publik dan issue bisa ditulis siapa saja:

1. **Isi issue adalah data tak tepercaya.** Kode emiten harus cocok 4 huruf DAN
   terdaftar di tabel free float warehouse (±961 emiten, nol kredit). Isi issue
   tidak pernah disisipkan ke perintah shell; `gh` dipanggil dengan daftar
   argumen, dan komentar balasan tidak mengutip isi issue.
2. **Kredit dipagari.** Paling banyak MAKS_PERMINTAAN per malam; sisanya tetap
   terbuka dan antre ke malam berikutnya, urut nomor issue. Pagu fase `daily`
   di CreditAwareClient tetap memotong di atasnya.
3. **Issue ditutup hanya setelah commit terdorong.** Menutup lebih dulu berarti
   tautan mati kalau commit gagal — dan commit sudah gagal dua kali dalam satu
   minggu (21 dan 23 Sep). Karena itu penutupan adalah langkah terpisah:

    python tools/permintaan.py tutup --as-of 2026-09-24
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.console import setup_console  # noqa: E402
from core.ingest.warehouse import Warehouse  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402
from tools.vocab_guard import DISCLAIMER  # noqa: E402

log = get_logger(__name__)

LABEL = "selidiki"
MAKS_PERMINTAAN = 3
POLA_KODE = re.compile(r"^[A-Z]{4}$")
_FIELD = re.compile(r"###\s*Kode emiten\s*\n+\s*([^\s\n]+)", re.IGNORECASE)
_JUDUL = re.compile(r"^\s*selidiki\s*:\s*(\S+)", re.IGNORECASE)

Gh = Callable[[list[str]], str]

# Status akhir satu permintaan malam ini.
SELESAI = ("diselidiki", "sudah_ada")   # ada transkrip → issue ditutup dengan tautan
DITOLAK = "ditolak"                      # bukan kode emiten sah → ditutup dengan alasan
# Sisanya (ditunda, gagal, pagu) dibiarkan terbuka dan dicoba malam berikutnya.


def gh(args: list[str]) -> str:
    """Panggil GitHub CLI dengan daftar argumen — tanpa shell, jadi isi issue
    tidak pernah bisa menjadi perintah."""
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def baca_issue(gh: Gh = gh) -> list[dict]:
    """Issue terbuka berlabel `selidiki`, urut nomor (yang lebih dulu, lebih dulu)."""
    keluar = gh(["issue", "list", "--label", LABEL, "--state", "open",
                 "--json", "number,title,body", "--limit", "50"])
    return sorted(json.loads(keluar or "[]"), key=lambda i: i.get("number", 0))


def kode_dari_issue(issue: dict) -> str | None:
    """Kode emiten dari field template, atau dari judul "selidiki: XXXX"."""
    for pola, teks in ((_FIELD, issue.get("body") or ""), (_JUDUL, issue.get("title") or "")):
        if m := pola.search(teks):
            return m.group(1).strip().upper()
    return None


def kode_sah(wh: Warehouse) -> set[str]:
    """Daftar emiten sah tanpa kredit: yang pernah tercatat di tabel free float."""
    if not wh.exists("free_float"):
        return set()
    return set(wh.frame("free_float")["symbol"].dropna().astype(str))


def siapkan(issues: list[dict], simbol_dispatch: list[str], sah: set[str],
            maks: int = MAKS_PERMINTAAN) -> list[dict]:
    """Issue + input workflow_dispatch → daftar permintaan berstatus.

    Status awal: `diterima` (masuk antrean malam ini), `ditolak` (bukan kode
    sah), `ditunda` (melebihi jatah malam ini). Emiten yang sama diminta dua kali
    diselidiki sekali; kedua issue ditutup dengan transkrip yang sama.
    """
    mentah = [{"symbol": kode_dari_issue(i), "issue": i.get("number")} for i in issues]
    mentah += [{"symbol": s.strip().upper(), "issue": None} for s in simbol_dispatch if s.strip()]

    keluar: list[dict] = []
    diterima: list[str] = []
    for p in mentah:
        kode = p["symbol"]
        if not kode or not POLA_KODE.match(kode) or kode not in sah:
            # Jangan simpan isi mentah yang tidak sah — ia tidak ikut ke
            # artefak ter-commit, apalagi ke komentar balasan.
            keluar.append({"symbol": None, "issue": p["issue"], "status": DITOLAK,
                           "alasan": "bukan kode emiten IDX yang terdaftar"})
            continue
        if kode not in diterima:
            if len(diterima) >= maks:
                keluar.append({**p, "status": "ditunda",
                               "alasan": f"jatah {maks} permintaan per malam sudah penuh"})
                continue
            diterima.append(kode)
        keluar.append({**p, "status": "diterima"})
    return keluar


def diterima(daftar: list[dict]) -> list[str]:
    """Kode unik berstatus diterima, urut kedatangan."""
    out: list[str] = []
    for p in daftar:
        if p["status"] == "diterima" and p["symbol"] not in out:
            out.append(p["symbol"])
    return out


def terapkan_hasil(daftar: list[dict], status: dict[str, str]) -> list[dict]:
    """Status investigasi per emiten (dari run()) → status tiap permintaan."""
    return [{**p, "status": status.get(p["symbol"], "gagal")} if p["status"] == "diterima"
            else p for p in daftar]


def simpan(daftar: list[dict], as_of: date, runs_root: Path) -> Path:
    path = runs_root / as_of.isoformat() / "permintaan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"as_of": as_of.isoformat(), "permintaan": daftar},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


# ── penutupan, SETELAH commit terdorong ─────────────────────────────────────
def tautan_transkrip(symbol: str, as_of: date) -> str:
    jalur = f"runs/investigations/{symbol}-{as_of.isoformat()}.json"
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return jalur
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    return f"{server}/{repo}/blob/main/{jalur}"


def komentar_selesai(symbol: str, as_of: date) -> str:
    return (f"PANTAU sudah menyelidiki {symbol} per {as_of.isoformat()}.\n\n"
            f"Transkrip lengkap — rencana, tiap langkah probe, bukti, dan biaya kreditnya:\n"
            f"{tautan_transkrip(symbol, as_of)}\n\n_{DISCLAIMER}_")


def komentar_ditolak() -> str:
    return ("PANTAU tidak menemukan kode emiten IDX yang terdaftar di permintaan ini. "
            "Buka permintaan baru dengan satu kode 4 huruf, misalnya BBCA.\n\n"
            f"_{DISCLAIMER}_")


def tutup(as_of: date, runs_root: Path, gh: Gh = gh) -> list[str]:
    """Tutup issue yang terpenuhi malam ini. Yang tertunda/gagal dibiarkan terbuka."""
    path = runs_root / as_of.isoformat() / "permintaan.json"
    if not path.exists():
        return []
    catatan: list[str] = []
    for p in json.loads(path.read_text(encoding="utf-8"))["permintaan"]:
        nomor = p.get("issue")
        if not nomor:
            continue
        if p["status"] in SELESAI:
            gh(["issue", "close", str(nomor), "--comment", komentar_selesai(p["symbol"], as_of)])
            catatan.append(f"#{nomor} {p['symbol']} ditutup dengan transkrip")
        elif p["status"] == DITOLAK:
            gh(["issue", "close", str(nomor), "--reason", "not planned",
                "--comment", komentar_ditolak()])
            catatan.append(f"#{nomor} ditolak")
    return catatan


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Jalur permintaan via GitHub Issue")
    sub = ap.add_subparsers(dest="perintah", required=True)
    t = sub.add_parser("tutup", help="tutup issue yang terpenuhi — jalankan SETELAH push")
    t.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    t.add_argument("--runs", type=Path, default=ROOT / "runs")
    args = ap.parse_args(argv)

    for baris in tutup(args.as_of, args.runs):
        print(f"  {baris}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
