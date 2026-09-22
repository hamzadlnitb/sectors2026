"""core/export/to_json.py — lapisan ekspor PANTAU (Nadhilla).

Baca transkrip investigasi (runs/investigations + fixtures) dan watchlist harian
(runs/<tgl>/watchlist.json), validasi terhadap kontrak beku, lalu tulis JSON
statis ke web/public/data/ untuk dikonsumsi web. Web hanya membaca berkas ini —
nol panggilan API/LLM saat runtime. [AD-1]

    python -m core.export.to_json            # tulis semua
    python -m core.export.to_json --check    # validasi saja, jangan tulis

Sumber transkrip:
  runs/investigations/*.json   ← keluaran agen (kanonik, dari cron)
  fixtures/transcripts/*.json   ← tiga keadaan UI beku (materi demo)

Keluaran:
  web/public/data/investigations/<SYM>-<YYYY-MM-DD>.json   ← transkrip tervalidasi
  web/public/data/index.json                               ← ringkasan untuk papan/route
  web/public/data/watchlist/<YYYY-MM-DD>.json              ← kandidat harian
  web/public/data/watchlist/index.json                     ← daftar tanggal watchlist
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# contracts/check.py (dan konsol Windows) memakai encoding bawaan OS — cp1252 di
# Windows — yang gagal pada byte non-ASCII di transkrip UTF-8. Mode UTF-8 Python
# membuat semua read_text & stdout default ke utf-8; jalankan ulang diri sekali.
if not sys.flags.utf8_mode and os.environ.get("PYTHONUTF8") != "1":
    import subprocess

    os.environ["PYTHONUTF8"] = "1"
    sys.exit(subprocess.run([sys.executable, "-X", "utf8", *sys.orig_argv[1:]]).returncode)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from contracts.check import check  # noqa: E402  (reuse invarian kontrak)
from contracts.schemas import InvestigationTranscript  # noqa: E402

WEB_DATA = ROOT / "web" / "public" / "data"
INV_OUT = WEB_DATA / "investigations"
WATCH_OUT = WEB_DATA / "watchlist"

REAL_SOURCE = ROOT / "runs" / "investigations"      # transkrip agen sungguhan (kanonik)
FIXTURE_SOURCE = ROOT / "fixtures" / "transcripts"  # placeholder UI — hanya untuk dev/test
WATCHLIST_GLOB = "runs/*/watchlist.json"

# Hilangkan em dash (—) dari teks yang tampil di web (permintaan desain UI). Aman:
# em dash hanya muncul di dalam nilai string JSON, tak pernah di sintaksnya, jadi
# menormalkannya di string serialisasi tidak merusak struktur.
_EMDASH = re.compile(r"\s*—\s*")


def _no_emdash(s: str) -> str:
    return _EMDASH.sub(", ", s)


def moment_kinds(t: InvestigationTranscript) -> list[str]:
    """Empat perilaku agentik, dibaca langsung dari transkrip — cermin dari
    lib/transcript.ts::detectMoments di web, supaya papan dan halaman detail
    tidak pernah menyimpang soal apa yang benar-benar dilakukan agen."""
    planned = {p for h in t.plan.hypotheses for p in h.probes}
    kinds: list[str] = []
    if any(s.probe not in planned for s in t.steps):
        kinds.append("adaptive")
    if any(s.next_action == "escalate" for s in t.steps):
        kinds.append("escalation")
    last = t.steps[-1] if t.steps else None
    if (
        last is not None
        and last.next_action == "conclude"
        and len(t.steps) < 6
        and t.credits_total < t.baseline_credits
    ):
        kinds.append("early_stop")
    if t.memory_ref:
        kinds.append("memory")
    return kinds


def savings_pct(t: InvestigationTranscript) -> int:
    if not t.baseline_credits:
        return 0
    return round((1 - t.credits_total / t.baseline_credits) * 100)


def headline(t: InvestigationTranscript) -> str:
    """Kalimat pertama narasi, dipangkas — ringkasan satu baris untuk kartu papan."""
    first = t.narrative.split(". ")[0].strip().rstrip(".")
    return (first[:117] + "…") if len(first) > 118 else first


def summarize(t: InvestigationTranscript, ident: str) -> dict:
    return {
        "id": ident,
        "symbol": t.symbol,
        "as_of": str(t.as_of),
        "pantau_score": t.pantau_score,
        "band": t.band,
        "confidence": t.confidence,
        # Berapa dari enam komponen yang benar-benar punya angka. Komposit
        # menormalkan ulang atas komponen yang TERSEDIA, jadi satu komponen
        # ekstrem sendirian menghasilkan skor 100 — tinggi justru karena agen
        # berhenti cepat, bukan karena buktinya kuat. Angka ini harus ikut
        # tampil di mana pun skor tampil, kalau tidak "100, 1 langkah, hemat"
        # terbaca sebagai efisien padahal artinya tipis.
        "components_used": sum(1 for c in t.components if c.sub_score is not None),
        "components_total": len(t.components),
        "steps": len(t.steps),
        "credits_total": t.credits_total,
        "baseline_credits": t.baseline_credits,
        "savings_pct": savings_pct(t),
        "memory_ref": t.memory_ref,
        "narrative_source": t.narrative_source,
        "moments": moment_kinds(t),
        "headline": headline(t),
        "trail": [
            {
                "probe": st.probe,
                "finding": st.finding,
                "credits": st.credits_spent,
                "planned": st.probe in {p for h in t.plan.hypotheses for p in h.probes},
            }
            for st in t.steps
        ],
    }


def collect_transcripts(sources: list[Path]) -> list[tuple[Path, InvestigationTranscript, list[str]]]:
    """Kembalikan (path, transkrip, error) untuk tiap berkas sumber."""
    out: list[tuple[Path, InvestigationTranscript, list[str]]] = []
    for src in sources:
        if not src.exists():
            continue
        for path in sorted(src.glob("*.json")):
            try:
                t = InvestigationTranscript.model_validate_json(path.read_text(encoding="utf-8"))
                errors = check(path)
            except Exception as exc:  # noqa: BLE001 — bentuk sama sekali tidak cocok
                out.append((path, None, [str(exc)]))  # type: ignore[arg-type]
                continue
            out.append((path, t, errors))
    return out


def write_investigations(check_only: bool, sources: list[Path]) -> tuple[list[dict], bool]:
    summaries: list[dict] = []
    failed = False

    if not check_only:
        INV_OUT.mkdir(parents=True, exist_ok=True)
        for old in INV_OUT.glob("*.json"):
            old.unlink()

    for path, t, errors in collect_transcripts(sources):
        if t is None or errors:
            failed = True
            print(f"✗ {path.name}")
            for e in errors:
                print(f"    {e}")
            continue

        ident = f"{t.symbol}-{t.as_of}"
        print(f"✓ {path.name} → {ident}")
        summaries.append(summarize(t, ident))

        if not check_only:
            # Tulis dari model tervalidasi, bukan salin mentah — normalisasi
            # bentuk & buang berkas yang tak lolos kontrak.
            (INV_OUT / f"{ident}.json").write_text(
                _no_emdash(t.model_dump_json(indent=2)), encoding="utf-8"
            )

    # Urut: skor tertinggi dulu, lalu tanggal terbaru.
    summaries.sort(key=lambda s: (-s["pantau_score"], s["as_of"]), reverse=False)
    summaries.sort(key=lambda s: (s["pantau_score"], s["as_of"]), reverse=True)
    return summaries, failed


def write_watchlists(check_only: bool) -> list[dict]:
    dates: list[dict] = []
    for path in sorted(ROOT.glob(WATCHLIST_GLOB)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"✗ watchlist {path}: {exc}")
            continue
        as_of = data.get("as_of") or path.parent.name
        # Sertakan run.log (bukti timestamp cron tak-ditunggui) di payload watchlist.
        log_path = path.parent / "run.log"
        if log_path.exists():
            data["run_log"] = log_path.read_text(encoding="utf-8").splitlines()
        dates.append(
            {
                "as_of": as_of,
                "generated_at": data.get("generated_at"),
                "credits_spent": data.get("credits_spent"),
                "candidates": len(data.get("candidates", [])),
            }
        )
        if not check_only:
            WATCH_OUT.mkdir(parents=True, exist_ok=True)
            (WATCH_OUT / f"{as_of}.json").write_text(
                _no_emdash(json.dumps(data, ensure_ascii=False, indent=2)), encoding="utf-8"
            )
        print(f"✓ watchlist {as_of} ({len(data.get('candidates', []))} kandidat)")

    dates.sort(key=lambda d: d["as_of"], reverse=True)
    if not check_only and dates:
        (WATCH_OUT / "index.json").write_text(
            _no_emdash(json.dumps({"dates": dates}, ensure_ascii=False, indent=2)), encoding="utf-8"
        )
    return dates


def build_activity(summaries: list[dict], watch_dates: list[dict]) -> dict:
    """Feed aktivitas agen (kronologis) untuk dashboard #4 — gabungan sapuan
    Tier-1 harian (Melco) + investigasi agen (Hamzah). Statis, dari runs/."""
    events: list[dict] = []
    for w in watch_dates:
        events.append({
            "ts": w.get("generated_at") or f"{w['as_of']}T00:00:00+00:00",
            "date": w["as_of"],
            "kind": "sweep",
            "candidates": w.get("candidates", 0),
            "credits": w.get("credits_spent"),
        })
    for s in summaries:
        events.append({
            "ts": f"{s['as_of']}T17:30:00+07:00",  # EOD WIB (transkrip hanya bertanggal)
            "date": s["as_of"],
            "kind": "investigation",
            "id": s["id"],
            "symbol": s["symbol"],
            "band": s["band"],
            "pantau_score": s["pantau_score"],
            "steps": s["steps"],
            "credits": s["credits_total"],
            "savings_pct": s["savings_pct"],
            "moments": s["moments"],
            "baseline_credits": s["baseline_credits"],
            "confidence": s["confidence"],
            "narrative_source": s["narrative_source"],
            "components_used": s["components_used"],
            "components_total": s["components_total"],
            "headline": s["headline"],
            "trail": s["trail"],
        })
    events.sort(key=lambda e: e["ts"], reverse=True)
    return {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "events": events}


def build_history(summaries: list[dict]) -> dict:
    """Riwayat analisa agen per emiten, terurut waktu.

    Feed aktivitas menjawab "agen ngapain hari ini". Ini menjawab pertanyaan yang
    justru membuktikan agennya berpikir: **apa yang berubah sejak terakhir kali
    ia melihat emiten yang sama.** Delta skor antar tanggal adalah satu-satunya
    tempat perilaku memori [ARCHITECTURE §3] terlihat tanpa harus membuka dua
    transkrip bersebelahan.

    Dihitung di sini, bukan di komponen, supaya papan dan landing memakai angka
    yang sama persis — delta yang dihitung dua kali adalah delta yang cepat atau
    lambat berbeda.
    """
    per_symbol: dict[str, list[dict]] = {}
    for s in summaries:
        per_symbol.setdefault(s["symbol"], []).append(s)

    keluar = []
    for symbol, rows in per_symbol.items():
        rows = sorted(rows, key=lambda r: r["as_of"])
        jejak = []
        for i, r in enumerate(rows):
            sebelum = rows[i - 1] if i else None
            jejak.append({
                "id": r["id"],
                "as_of": r["as_of"],
                "pantau_score": r["pantau_score"],
                "band": r["band"],
                "confidence": r["confidence"],
                "steps": r["steps"],
                "credits_total": r["credits_total"],
                "savings_pct": r["savings_pct"],
                "moments": r["moments"],
                "narrative_source": r["narrative_source"],
                "components_used": r["components_used"],
                "components_total": r["components_total"],
                "headline": r["headline"],
                "trail": r["trail"],
                # None pada kunjungan pertama — "belum pernah dilihat" dan
                # "tidak berubah" adalah dua hal berbeda, dan UI harus bisa
                # membedakannya.
                "delta_score": (r["pantau_score"] - sebelum["pantau_score"]) if sebelum else None,
                "delta_band": (r["band"] != sebelum["band"]) if sebelum else None,
            })
        skor = [j["pantau_score"] for j in jejak]
        keluar.append({
            "symbol": symbol,
            "kunjungan": len(jejak),
            "pertama": jejak[0]["as_of"],
            "terakhir": jejak[-1]["as_of"],
            "skor_terakhir": jejak[-1]["pantau_score"],
            "band_terakhir": jejak[-1]["band"],
            "skor_min": min(skor),
            "skor_maks": max(skor),
            "kredit_total": sum(j["credits_total"] for j in jejak),
            "jejak": jejak,
        })

    # Yang paling sering dikunjungi lebih dulu: emiten dengan riwayat terpanjang
    # adalah yang paling menunjukkan agen bekerja berulang, bukan sekali jalan.
    keluar.sort(key=lambda e: (-e["kunjungan"], -e["skor_terakhir"]))
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "symbols": keluar,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Ekspor transkrip + watchlist ke web/public/data")
    ap.add_argument("--check", action="store_true", help="validasi saja, jangan tulis")
    ap.add_argument("--with-fixtures", action="store_true",
                    help="sertakan fixtures/transcripts (default: hanya transkrip asli runs/investigations)")
    args = ap.parse_args()

    sources = [REAL_SOURCE] + ([FIXTURE_SOURCE] if args.with_fixtures else [])
    summaries, failed = write_investigations(args.check, sources)
    watch_dates = write_watchlists(args.check)

    if not args.check:
        WEB_DATA.mkdir(parents=True, exist_ok=True)
        index = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "investigations": summaries,
            "watchlist_dates": watch_dates,
        }
        (WEB_DATA / "index.json").write_text(
            _no_emdash(json.dumps(index, ensure_ascii=False, indent=2)), encoding="utf-8"
        )
        activity = build_activity(summaries, watch_dates)
        (WEB_DATA / "activity.json").write_text(
            _no_emdash(json.dumps(activity, ensure_ascii=False, indent=2)), encoding="utf-8"
        )
        history = build_history(summaries)
        (WEB_DATA / "history.json").write_text(
            _no_emdash(json.dumps(history, ensure_ascii=False, indent=2)), encoding="utf-8"
        )
        print(f"\n→ {len(summaries)} investigasi, {len(watch_dates)} watchlist, "
              f"{len(activity['events'])} aktivitas, {len(history['symbols'])} emiten berriwayat "
              f"ditulis ke {WEB_DATA.relative_to(ROOT)}")

    if failed:
        print("\n✗ ada transkrip yang tidak lolos kontrak — tidak diekspor.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
