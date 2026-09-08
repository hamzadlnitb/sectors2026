"""Backfill historis untuk kalibrasi bobot. Anggaran 400 kredit. [M3]

Hamzah **terblokir total** tanpa ini: tanpa riwayat, tidak ada himpunan positif,
tidak ada bobot terkalibrasi, dan Angka 1 tidak pernah ada.

Tiga tarikan, dari yang paling murah dan paling menentukan:

    1. riwayat harga alam semesta kandidat         2 kredit / ticker
    2. peristiwa market-wide 24 bulan (paginasi)   ±10 kredit
    3. Tier-2 untuk himpunan positif + kontrol     ±10 kredit / ticker

⚠️  **Rencana ini pernah salah besar, dan koreksinya penting.** Versi pertama
    menarik `fetch-close` sekali per hari bursa, mengira satu panggilan = seluruh
    ticker. Katalog MCP Sectors menyatakan sebaliknya: `fetch-close` berbayar
    **1 kredit per halaman**, limit maks 30, jadi seluruh ~950 ticker = ~32
    kredit **per hari**. Rencana 120 hari itu berarti **~3.840 kredit** — hampir
    empat kali seluruh jatah tim, untuk satu tahap saja.

    Gantinya `fetch-daily-transaction`: **1 kredit untuk rentang sampai 90 hari**
    per ticker. Konsekuensinya alam semesta harus dipersempit lebih dulu (itu
    memang sudah ada di TASK.md §Rencana Cadangan), dan justru itu yang membuat
    anggaran masuk akal: 80 ticker x 2 panggilan = 160 kredit untuk 180 hari
    riwayat, bukan 3.840 untuk 120 hari.

Urutannya bukan selera: tarikan 1 dan 2 menentukan SIAPA yang masuk himpunan
positif, dan tarikan 3 baru bisa direncanakan setelah keduanya selesai.
Menjalankan 3 lebih dulu berarti menebak, dan menebak di sini berharga 250 kredit.

**Selalu jalankan --dry-run lebih dulu.** Ia mencetak rencana lengkap berikut
biayanya tanpa memanggil apa pun — satu-satunya cara mengetahui ongkos sebelum
membayarnya, dan pagu fase ditegakkan dengan raise, bukan peringatan.

    python -m core.ingest.backfill --dry-run
    python -m core.ingest.backfill --stage 1
    python -m core.ingest.backfill --stage 3 --positives runs/positives.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from core.console import setup_console
from core.ingest.warehouse import Warehouse
from core.sectors.client import CreditAwareClient
from core.sectors.errors import BudgetExceeded, SectorsError
from core.sectors.ledger import CreditLedger
from core.sectors.redact import get_logger
from core.sectors.routing import cost_of

log = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]

SESI_HARGA = 120
BULAN_PERISTIWA = 24
PHASE = "backfill"

# Alasan suspensi yang menandakan pergerakan/aktivitas tidak wajar. Ini SUMBER
# LABEL kalibrasi — kalau daftar ini berubah, himpunan positif Hamzah bergeser.
# Sinkron dengan core/probes/structural.py; kabari dia kalau diubah.
ALASAN_POSITIF = (
    "tidak wajar", "di luar kebiasaan", "unusual", "uma",
    "pergerakan harga", "peningkatan harga", "aktivitas transaksi",
)

# Tier-2 yang ditarik untuk tiap ticker di himpunan positif + kontrol.
# fetch-free-float SENGAJA tidak di sini: ia berbayar 1 kredit per 100 emiten dan
# bisa ditarik TANPA filter symbol, jadi ~10 kredit menutup free float SELURUH
# IDX sekaligus. Menariknya per emiten berarti membayar 1 kredit untuk satu baris
# yang sudah termasuk dalam tarikan market-wide. Lihat MARKET_WIDE.
TIER2_PER_TICKER = (
    "fetch-company-report",
    "fetch-filings",
    "fetch-daily-transaction",
    "fetch-broker-summary-top",
    "fetch-foreign-flow",
    "fetch-quarterly-financials",
    "fetch-corporate-actions",
)

TABEL_TIER2 = {
    "fetch-company-report": "company_profile",
    "fetch-filings": "filings",
    "fetch-daily-transaction": "daily_transaction",
    "fetch-broker-summary-top": "broker_summary",
    "fetch-foreign-flow": "foreign_flow",
    "fetch-free-float": "free_float",
    "fetch-quarterly-financials": "quarterly_financials",
    "fetch-corporate-actions": "corporate_actions",
}


@dataclass
class Plan:
    """Rencana belanja sebelum satu kredit pun keluar."""

    stage: int
    calls: list[tuple[str, dict]] = field(default_factory=list)

    @property
    def credits(self) -> int:
        return sum(cost_of(name) for name, _ in self.calls)

    def describe(self) -> str:
        per_endpoint: dict[str, list[int]] = {}
        for name, _ in self.calls:
            per_endpoint.setdefault(name, []).append(cost_of(name))
        lines = [f"TAHAP {self.stage} — {len(self.calls)} panggilan, {self.credits} kredit"]
        for name, biaya in sorted(per_endpoint.items(), key=lambda kv: -sum(kv[1])):
            lines.append(f"  {name:<32} {len(biaya):>4}x  {sum(biaya):>4} kredit")
        return "\n".join(lines)


def _bulan_lalu(as_of: date, bulan: int) -> date:
    tahun = as_of.year - (bulan // 12)
    sisa = as_of.month - (bulan % 12)
    if sisa <= 0:
        sisa += 12
        tahun -= 1
    return as_of.replace(year=tahun, month=sisa, day=1)


def _hari_kerja(as_of: date, count: int) -> list[date]:
    """Perkiraan hari bursa mundur dari as_of.

    Libur nasional IDX tidak dimodelkan, jadi sebagian tanggal akan mengembalikan
    respons kosong. Itu disengaja dan murah: satu panggilan kosong lebih baik
    daripada satu hari bursa yang bolong di riwayat kalibrasi.
    """
    out, cursor = [], as_of
    while len(out) < count:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(out)


# ── perencanaan ─────────────────────────────────────────────────────────────
JENDELA_MAKS = 90
"""Batas keras fetch-daily-transaction. Rentang lebih lebar dipangkas server."""


def plan_stage1(as_of: date, symbols: list[str], sessions: int = SESI_HARGA) -> Plan:
    """Riwayat harga & volume untuk alam semesta kandidat.

    Per ticker, bukan per hari. Lihat catatan di kepala berkas: menarik seluruh
    pasar per hari lewat fetch-close berharga ~32 kredit/hari dan mustahil dibiayai.
    """
    calls: list[tuple[str, dict]] = []
    for symbol in symbols:
        akhir = as_of
        sisa = sessions
        while sisa > 0:
            mulai = akhir - timedelta(days=int(JENDELA_MAKS * 1.5))
            calls.append(("fetch-daily-transaction", {
                "symbol": symbol, "start": mulai.isoformat(), "end": akhir.isoformat(),
            }))
            sisa -= JENDELA_MAKS
            akhir = mulai - timedelta(days=1)
    return Plan(1, calls)


def universe(wh: Warehouse, as_of: date, size: int = 80) -> list[str]:
    """Alam semesta kandidat dari data yang SUDAH ada di warehouse — nol kredit.

    Diambil dari ticker yang paling sering muncul di sapuan Tier-1 harian,
    ditambah seluruh emiten yang pernah disuspend (mereka wajib ada di himpunan
    positif). Ini penyempitan yang disebut TASK.md §Rencana Cadangan, dilakukan
    lebih awal karena anggaran memaksanya, bukan karena kredit menipis.
    """
    sering: list[str] = []
    trans = wh.frame("daily_transaction", as_of=as_of)
    if not trans.empty:
        sering = trans["symbol"].value_counts().head(size).index.tolist()

    susp = wh.frame("suspensions", as_of=as_of)
    wajib = susp["symbol"].unique().tolist() if not susp.empty else []

    keluar = list(dict.fromkeys([*wajib, *sering]))
    return keluar[:size]


# Baris per halaman untuk endpoint berpaginasi. Spike F0: bawaannya 20, dan
# fetch-suspensions punya 533 baris dalam 24 bulan. Minta halaman sebesar
# mungkin — tiap halaman satu panggilan, dan tiap panggilan satu kredit.
PAGE_SIZE = 100
"""Yang KITA minta. Server berhak memangkasnya — dan Sectors memangkasnya."""

PAGE_SIZE_NYATA = 30
"""Yang benar-benar dikirim server, diukur 8 Sep: 534 suspensi terambil dalam 18
panggilan. Perkiraan halaman WAJIB memakai angka ini; memakai PAGE_SIZE membuat
rencana meleset 3x dan itulah yang bikin tahap 2 menghabiskan 68 kredit untuk
anggaran 9."""

PAGU_HALAMAN = {"fetch-suspensions": 25}
"""Pagu kredit per endpoint saat menelusuri halaman. Pagar halaman saja tidak
tahu harga: fetch-filings pernah menembus 50 halaman = 50 kredit tanpa
peringatan, lalu kena 429 dan hasilnya hangus."""

MARKET_WIDE: tuple[tuple[str, dict, str], ...] = (
    # (endpoint, params, tabel). Ditarik sekali untuk seluruh pasar karena
    # harganya per-100-emiten, bukan per-emiten.
    ("fetch-free-float", {}, "free_float"),
)
PAGU_MARKET_WIDE = 12
"""~950 emiten / 100 per kredit = ~10, plus ruang kalau jumlahnya bertambah."""

BERPAGINASI = ("fetch-suspensions",)
"""Hanya suspensi yang ditarik market-wide.

fetch-filings market-wide 24 bulan diukur berharga ~600 kredit — 75 kredit cuma
membeli 3 bulan dari 24. Padahal kalibrasi tidak butuh seluruh pasar: yang
diperlukan filing di sekitar peristiwa, untuk emiten di himpunan positif dan
kontrolnya saja. Karena itu filings pindah ke tahap 3, per emiten (1 kredit),
dan sapuan harian tetap menjaga yang berjalan."""


def _perkiraan_halaman(total: int, per_halaman: int = PAGE_SIZE_NYATA) -> int:
    return max(1, -(-total // per_halaman))


# Total baris yang dilaporkan spike 8 Sep untuk rentang 24 bulan. Dipakai untuk
# MENGANGGARKAN, bukan sebagai kebenaran — jumlah asli akan berbeda saat backfill
# benar-benar jalan, dan itu tidak apa-apa selama pagu fase tetap ditegakkan.
TOTAL_TERAMATI = {"fetch-suspensions": 534}


def plan_stage2(as_of: date, bulan: int = BULAN_PERISTIWA) -> Plan:
    """Suspensi & filings market-wide, satu rentang penuh, ditelusuri per halaman.

    Sebelumnya rencana ini memecah per bulan dan MENGABAIKAN paginasi. Spike F0
    membuktikan itu salah: fetch-suspensions melaporkan total_count 533 sementara
    satu panggilan cuma mengirim 20 baris. Rencana lama akan menarik 25 potong
    berisi 20 baris pertama masing-masing, lalu mengira 24 bulan sudah lengkap —
    dan himpunan positif Hamzah jadi sepotong tanpa ada yang sadar.

    Rentang penuh + paginasi lebih murah SEKALIGUS lebih lengkap: satu jendela
    dengan halaman 100 baris menghabiskan ~6 panggilan untuk suspensi, bukan 25.
    """
    mulai = _bulan_lalu(as_of, bulan)
    window = {"start": mulai.isoformat(), "end": as_of.isoformat()}
    calls: list[tuple[str, dict]] = []
    for endpoint in BERPAGINASI:
        halaman = min(PAGU_HALAMAN.get(endpoint, 25),
                      _perkiraan_halaman(TOTAL_TERAMATI.get(endpoint, PAGE_SIZE_NYATA)))
        for i in range(halaman):
            calls.append((endpoint, {**window, "limit": PAGE_SIZE, "offset": i * PAGE_SIZE}))
    return Plan(2, calls)


def plan_stage3(symbols: list[str], as_of: date, sessions: int = SESI_HARGA) -> Plan:
    mulai = _hari_kerja(as_of, sessions)[0].isoformat()
    calls: list[tuple[str, dict]] = []
    for symbol in symbols:
        for endpoint in TIER2_PER_TICKER:
            params: dict = {"symbol": symbol}
            if endpoint in ("fetch-daily-transaction", "fetch-broker-summary-top",
                            "fetch-foreign-flow", "fetch-corporate-actions",
                            "fetch-filings"):
                params |= {"start": mulai, "end": as_of.isoformat()}
            if endpoint == "fetch-quarterly-financials":
                params |= {"n_quarters": 8}
            calls.append((endpoint, params))
    return Plan(3, calls)


# ── himpunan positif & kontrol ──────────────────────────────────────────────
def positives(wh: Warehouse, as_of: date) -> list[dict]:
    """Suspensi yang alasannya terkait pergerakan/aktivitas tidak wajar.

    Ini yang diserahkan ke Hamzah sebagai himpunan positif, LENGKAP DENGAN
    ALASAN RESMINYA — bukan cuma daftar ticker. Penyaringannya bisa dan harus
    dia periksa ulang; suspensi bukan sinonim manipulasi, dan batasan itu
    ditulis terbuka di halaman Metodologi. [ARCHITECTURE §6]
    """
    df = wh.frame("suspensions", as_of=as_of)
    if df.empty:
        return []
    batas = _bulan_lalu(as_of, BULAN_PERISTIWA)
    df = df[pd.to_datetime(df["start_date"]).dt.date >= batas]
    out = []
    for _, row in df.iterrows():
        alasan = str(row.get("reason") or "")
        cocok = [k for k in ALASAN_POSITIF if k in alasan.lower()]
        out.append({
            "symbol": row["symbol"],
            "start_date": str(pd.to_datetime(row["start_date"]).date()),
            "reason": alasan,
            "matched_keywords": cocok,
            "is_positive": bool(cocok),
        })
    return sorted(out, key=lambda r: (not r["is_positive"], r["start_date"]))


def controls(wh: Warehouse, as_of: date, positif: list[str], per_positif: int = 2) -> list[str]:
    """Kontrol tersamakan berdasarkan subsektor & kapitalisasi terdekat.

    Tersamakan, bukan acak: kalau kontrolnya bank besar sementara positifnya
    saham lapis tiga, model akan belajar membedakan ukuran perusahaan dan
    terlihat hebat tanpa mendeteksi apa pun. [ARCHITECTURE §6 langkah 2]
    """
    profil = wh.frame("company_profile", as_of=as_of)
    if profil.empty:
        return []
    profil = profil[profil["market_cap"].notna()]
    dipakai = set(positif)
    keluar: list[str] = []

    for symbol in positif:
        baris = profil[profil["symbol"] == symbol]
        if baris.empty:
            continue
        cap = float(baris.iloc[0]["market_cap"])
        subsektor = baris.iloc[0]["sub_sector"]
        kandidat = profil[(profil["sub_sector"] == subsektor)
                          & (~profil["symbol"].isin(dipakai))].copy()
        if kandidat.empty:
            continue
        kandidat["jarak"] = (kandidat["market_cap"].astype(float) - cap).abs()
        for pilih in kandidat.nsmallest(per_positif, "jarak")["symbol"]:
            dipakai.add(pilih)
            keluar.append(pilih)
    return keluar


# ── eksekusi ────────────────────────────────────────────────────────────────
def execute(plan: Plan, client: CreditAwareClient, wh: Warehouse,
            table_for) -> tuple[int, list[str]]:
    """Jalankan rencana. Berhenti rapi kalau pagu tertembus."""
    spent, gagal = 0, []
    for i, (endpoint, params) in enumerate(plan.calls, 1):
        try:
            rows, resp = client.rows(endpoint, params, phase=PHASE,
                                     symbol=params.get("symbol"))
        except BudgetExceeded as exc:
            # Pagu habis bukan bug: berhenti dengan data yang sudah terkumpul,
            # laporkan berapa yang tersisa. Backfill separuh masih berguna.
            gagal.append(f"pagu habis di panggilan {i}/{len(plan.calls)}: {exc}")
            break
        except SectorsError as exc:
            gagal.append(f"{endpoint} {params}: {exc}")
            continue

        spent += resp.credits_spent
        if rows:
            wh.write(table_for(endpoint), rows)
        if i % 20 == 0:
            log.info("tahap %d: %d/%d panggilan, %d kredit", plan.stage, i, len(plan.calls), spent)
    return spent, gagal


def _stempel_as_of(rows: list, as_of: date) -> list:
    """Isi as_of yang kosong dengan tanggal tarikan.

    fetch-free-float TIDAK mengirim tanggal berlaku — 961 baris, semuanya tanpa
    as_of. Tanpa stempel, penyaring point-in-time membuang seluruhnya dan
    komponen FFS mati untuk semua emiten.

    Stempelnya tanggal TARIKAN, bukan tanggal berlaku yang sebenarnya, dan itu
    perbedaan yang penting: kalibrasi pada T-10 tidak akan melihat baris ini,
    karena kita memang TIDAK TAHU free float pada T-10. Itu perilaku yang benar —
    memakai angka hari ini untuk tanggal lampau adalah lookahead, persis yang
    dilarang C1. Konsekuensinya FFS tidak bisa ikut kalibrasi historis sampai
    Sectors menyediakan riwayatnya; dicatat terbuka, bukan disembunyikan.
    """
    for r in rows:
        if getattr(r, "as_of", "tidak ada") is None:
            r.as_of = as_of
    return rows


def execute_paginated(client: CreditAwareClient, wh: Warehouse, as_of: date,
                      dry_run: bool = False) -> tuple[int, list[str]]:
    """Tahap 2: telusuri seluruh halaman, jangan berhenti di halaman pertama."""
    mulai = _bulan_lalu(as_of, BULAN_PERISTIWA)
    window = {"start": mulai.isoformat(), "end": as_of.isoformat()}
    spent, gagal = 0, []

    for endpoint, params, tabel in MARKET_WIDE:
        try:
            rows, credits = client.paginate(
                endpoint, {**params, **window} if "start" in params else params,
                page_size=PAGE_SIZE, phase=PHASE, max_credits=PAGU_MARKET_WIDE,
            )
        except SectorsError as exc:
            gagal.append(f"{endpoint}: {exc}")
        else:
            spent += credits
            if rows:
                wh.write(tabel, _stempel_as_of(rows, as_of))
            print(f"  {endpoint:<24} {len(rows):>5} baris, {credits} kredit (market-wide)")

    for endpoint in BERPAGINASI:
        try:
            rows, credits = client.paginate(
                endpoint, window, page_size=PAGE_SIZE, phase=PHASE,
                max_credits=PAGU_HALAMAN.get(endpoint, 25),
            )
        except BudgetExceeded as exc:
            gagal.append(f"pagu habis saat menelusuri {endpoint}: {exc}")
            break
        except SectorsError as exc:
            gagal.append(f"{endpoint}: {exc}")
            continue

        spent += credits
        if rows:
            wh.write(TABEL_TAHAP12[endpoint], rows)
        print(f"  {endpoint:<24} {len(rows):>5} baris, {credits} kredit")
    return spent, gagal


TABEL_TAHAP12 = {
    "fetch-close": "daily_close",
    "fetch-suspensions": "suspensions",
    "fetch-filings": "filings",
}


def _saran_penyempitan(sisa: int, as_of: date, alam_semesta: list[str]) -> str:
    """Berapa emiten yang MASIH muat di sisa pagu.

    Menolak rencana tanpa memberi angka pengganti cuma memindahkan pekerjaan
    berhitung ke orang yang sedang buru-buru — dan di situlah kredit terbakar.
    """
    per_riwayat = plan_stage1(as_of, ["XXXX"]).credits          # tahap 1 per emiten
    per_tier2 = plan_stage3(["XXXX"], as_of).credits            # tahap 3 per emiten
    peristiwa = plan_stage2(as_of).credits

    ruang = max(0, sisa - peristiwa)
    baris = [
        "",
        f"Muat di sisa {sisa} kredit (tahap 2 sudah termasuk {peristiwa}):",
        f"  riwayat harga saja      : {ruang // per_riwayat} emiten "
        f"({per_riwayat} kredit/emiten)",
        f"  riwayat + Tier-2 penuh  : {ruang // (per_riwayat + per_tier2)} emiten "
        f"({per_riwayat + per_tier2} kredit/emiten)",
        "",
        "Persempit dengan --symbols, atau turunkan --sessions.",
    ]
    if alam_semesta:
        baris.append(f"Alam semesta saat ini {len(alam_semesta)} emiten.")
    return "\n".join(baris)


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Backfill historis PANTAU (fase backfill, 400 kredit)")
    ap.add_argument("--stage", type=int, choices=(1, 2, 3), help="tanpa ini: cetak semua rencana")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--sessions", type=int, default=SESI_HARGA)
    ap.add_argument("--warehouse", type=Path, default=None)
    ap.add_argument("--symbols", nargs="*", default=None,
                    help="tahap 3: daftar ticker eksplisit")
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "backfill",
                    help="tempat himpunan positif & kontrol diserahkan ke Hamzah")
    ap.add_argument("--dry-run", action="store_true",
                    help="cetak rencana dan biayanya, jangan panggil apa pun")
    args = ap.parse_args(argv)

    wh = Warehouse(args.warehouse)
    ledger = CreditLedger()

    if args.stage in (None, 3) and not args.symbols:
        positif = [p for p in positives(wh, args.as_of) if p["is_positive"]]
        simbol_positif = sorted({p["symbol"] for p in positif})
        simbol = simbol_positif + controls(wh, args.as_of, simbol_positif)
    else:
        positif, simbol = [], list(args.symbols or [])

    alam_semesta = list(args.symbols) if args.symbols else universe(wh, args.as_of)
    rencana = {
        1: plan_stage1(args.as_of, alam_semesta, args.sessions),
        2: plan_stage2(args.as_of),
        3: plan_stage3(simbol, args.as_of, args.sessions),
    }

    if args.stage is None or args.dry_run:
        total = 0
        for stage in (1, 2, 3):
            print(rencana[stage].describe())
            total += rencana[stage].credits
            print()
        print(f"TOTAL RENCANA           {total} kredit")
        print(f"alam semesta tahap 1    {len(alam_semesta)} ticker"
              f"{' (kosong — jalankan sapuan Tier-1 dulu)' if not alam_semesta else ''}")
        print(f"pagu fase backfill      {ledger.caps['backfill']} kredit "
              f"(terpakai {ledger.spent(PHASE)}, sisa {ledger.remaining(PHASE)})")
        if simbol:
            print(f"\nhimpunan positif ({len(set(s['symbol'] for s in positif))}) + kontrol "
                  f"= {len(simbol)} ticker: {', '.join(simbol[:12])}"
                  f"{' …' if len(simbol) > 12 else ''}")
        elif args.stage in (None, 3):
            print("\ntahap 3 belum bisa direncanakan: himpunan positif kosong. "
                  "Jalankan tahap 2 lebih dulu.")
        sisa = ledger.remaining(PHASE)
        if total > sisa:
            print(f"\n⚠ rencana {total} kredit melebihi sisa pagu {sisa} — dihentikan "
                  f"sebelum satu panggilan pun keluar.")
            print(_saran_penyempitan(sisa, args.as_of, alam_semesta))
            return 2
        return 0

    plan = rencana[args.stage]
    print(plan.describe())
    table_for = (lambda e: TABEL_TIER2[e]) if args.stage in (1, 3) else (
        lambda e: TABEL_TAHAP12[e])

    with CreditAwareClient(phase=PHASE, ledger=ledger,
                           run_id=f"backfill-{args.as_of}") as client:
        if args.stage == 2:
            spent, gagal = execute_paginated(client, wh, args.as_of, args.dry_run)
        else:
            spent, gagal = execute(plan, client, wh, table_for)

    print(f"\n{spent} kredit terpakai; {client.stats.summary()}")
    print(wh.describe())

    if args.stage == 2:
        # Serahkan ke Hamzah: himpunan positif MENTAH beserta alasan resminya,
        # supaya penyaringannya bisa dia periksa ulang sendiri.
        args.out.mkdir(parents=True, exist_ok=True)
        semua = positives(wh, args.as_of)
        (args.out / "suspensions-labeled.json").write_text(
            json.dumps({
                "as_of": args.as_of.isoformat(),
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "keywords": list(ALASAN_POSITIF),
                "total": len(semua),
                "positives": sum(1 for s in semua if s["is_positive"]),
                "rows": semua,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"himpunan positif diserahkan ke {args.out / 'suspensions-labeled.json'}")

    if gagal:
        print(f"\n{len(gagal)} masalah:", *gagal[:10], sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
