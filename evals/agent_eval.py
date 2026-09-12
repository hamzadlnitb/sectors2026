"""Angka 2 — apakah perencanaan agen bernilai lebih daripada aturan sederhana?

    python3 evals/agent_eval.py --offline          # FakeLLM, nol jaringan
    python3 evals/agent_eval.py --tulis            # LLM sungguhan, tulis laporan
    python3 evals/agent_eval.py --limit 4          # cicip cepat

Empat lengan dibandingkan pada emiten yang sama (`evals/arms.py`), plus satu
pembanding kelima: perencana yang **tidak melihat harga kredit** di katalognya.

Yang dilaporkan:

* **kredit terhitung** per lengan — hemat dibanding menyeluruh
* **kesepakatan band** terhadap lengan menyeluruh; hemat tanpa kesepakatan tidak
  ada artinya, karena berhenti di langkah pertama selalu paling hemat
* **presisi eskalasi** — ketika agen membuka probe di luar rencana, seberapa sering
  itu benar-benar mengubah band. Eskalasi yang tidak pernah mengubah apa pun adalah
  teater, bukan perutean adaptif
* **kepekaan harga** — agen vs agen-tanpa-harga. Kalau pilihannya sama saja,
  "pemilihan tool sadar biaya" cuma sebutan dan klaim itu harus dicabut [AD-7]
"""

from __future__ import annotations

import argparse
import json
import statistics as stat
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ingest.warehouse import Warehouse  # noqa: E402
from core.probes.base import Context  # noqa: E402
from core.scoring.composite import score  # noqa: E402
from evals import arms  # noqa: E402
from evals.build_cases import muat  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LAPORAN = ROOT / "reports" / "agent-eval.md"
HASIL = ROOT / "runs" / "evals"


@dataclass
class Baris:
    symbol: str
    per_lengan: dict[str, arms.ArmResult] = field(default_factory=dict)

    @property
    def baseline(self) -> int:
        return arms.baseline_credits(self.symbol)


def _ctx(as_of: date) -> Context:
    # client=None: eval tidak pernah membelanjakan kredit. Satuan biayanya
    # cost_estimate, lihat docstring evals/arms.py.
    return Context(as_of=as_of, warehouse=Warehouse(), client=None, phase="eval")


def _llm(offline: bool):
    if offline:
        from core.llm import FakeLLM
        return FakeLLM()  # tiap permintaan gagal → jalur cadangan deterministik
    from core.llm import LLM
    return LLM.from_env(eval_mode=True)


def jalankan(kasus: list[dict], *, as_of: date, offline: bool) -> list[Baris]:
    llm = _llm(offline)
    keluar: list[Baris] = []

    for k in kasus:
        sym = k["symbol"]
        baris = Baris(symbol=sym)

        baris.per_lengan["menyeluruh"] = arms.menyeluruh(sym, _ctx(as_of))
        a = arms.agen(sym, _ctx(as_of), llm, as_of=as_of, show_price=True)
        baris.per_lengan["agen"] = a

        # Pembanding diberi pagu SAMA dengan yang benar-benar dipakai agen.
        # Tanpa penyamaan ini kita cuma membuktikan "menjalankan lebih sedikit
        # probe lebih murah", yang tidak perlu dibuktikan.
        pagu = max(a.credits, 1)
        baris.per_lengan["urutan_tetap"] = arms.urutan_tetap(sym, _ctx(as_of), pagu)
        baris.per_lengan["acak"] = arms.acak(sym, _ctx(as_of), pagu)
        baris.per_lengan["agen_tanpa_harga"] = arms.agen(
            sym, _ctx(as_of), llm, as_of=as_of, show_price=False)

        keluar.append(baris)
        print(f"  {sym}  agen {a.credits:2d}/{baris.baseline} kredit, "
              f"band {a.band} ({a.steps} langkah)")
    return keluar


def presisi_eskalasi(baris: list[Baris], as_of: date) -> tuple[int, int]:
    """(berguna, total). Berguna = tanpa probe eskalasi itu, band akan berbeda."""
    total = berguna = 0
    for b in baris:
        a = b.per_lengan.get("agen")
        if not a:
            continue
        for probe in a.escalated:
            total += 1
            tanpa = {k: v for k, v in a.results.items() if k != probe}
            if score(tanpa).band != a.band:
                berguna += 1
    return berguna, total


def ringkas(baris: list[Baris], as_of: date) -> dict:
    lengan = ["menyeluruh", "agen", "urutan_tetap", "acak", "agen_tanpa_harga"]
    acuan = {b.symbol: b.per_lengan["menyeluruh"].band for b in baris}

    ringkasan: dict = {"as_of": as_of.isoformat(), "n_kasus": len(baris), "lengan": {}}
    for nama in lengan:
        kredit = [b.per_lengan[nama].credits for b in baris if nama in b.per_lengan]
        sepakat = sum(1 for b in baris
                      if nama in b.per_lengan
                      and b.per_lengan[nama].band == acuan[b.symbol])
        n = len(kredit) or 1
        baseline = sum(b.baseline for b in baris) or 1
        ringkasan["lengan"][nama] = {
            "kredit_rata2": round(stat.mean(kredit), 2) if kredit else 0,
            "kredit_total": sum(kredit),
            "hemat_persen": round(100 * (1 - sum(kredit) / baseline), 1),
            "sepakat_band": sepakat,
            "sepakat_persen": round(100 * sepakat / n, 1),
        }

    berguna, total = presisi_eskalasi(baris, as_of)
    ringkasan["eskalasi"] = {
        "total": total, "mengubah_band": berguna,
        "presisi_persen": round(100 * berguna / total, 1) if total else None,
    }

    beda = sum(1 for b in baris
               if b.per_lengan["agen"].probes_run != b.per_lengan["agen_tanpa_harga"].probes_run)
    ringkasan["kepekaan_harga"] = {
        "kasus_pilihan_berbeda": beda,
        "persen": round(100 * beda / (len(baris) or 1), 1),
    }
    ringkasan["perencana_llm"] = sum(1 for b in baris if b.per_lengan["agen"].planner_llm)
    return ringkasan


def render(r: dict, baris: list[Baris]) -> str:
    L = r["lengan"]
    out = [
        "# reports/agent-eval.md — Angka 2",
        "",
        f"_{r['n_kasus']} emiten, tanggal acuan {r['as_of']}. Dibangkitkan "
        "`python3 evals/agent_eval.py --tulis`._",
        "",
        "Satuan biaya adalah **kredit terhitung** — jumlah `cost_estimate()` probe yang "
        "dijalankan, yaitu biaya seandainya warehouse kosong. Eval berjalan dengan "
        "`client=None` sehingga nol kredit benar-benar terbakar. Alasannya di docstring "
        "`evals/arms.py`: kredit terbakar mengukur keberuntungan cache, bukan kualitas "
        "perencanaan.",
        "",
        "## Hasil",
        "",
        "| Lengan | Kredit rata-rata | Hemat vs menyeluruh | Sepakat band |",
        "| --- | --- | --- | --- |",
    ]
    label = {"menyeluruh": "Menyeluruh (acuan)", "agen": "**Agen**",
             "urutan_tetap": "Urutan tetap", "acak": "Acak berpagu sama",
             "agen_tanpa_harga": "Agen tanpa lihat harga"}
    for nama in ("menyeluruh", "agen", "urutan_tetap", "acak", "agen_tanpa_harga"):
        d = L[nama]
        out.append(f"| {label[nama]} | {d['kredit_rata2']} | {d['hemat_persen']}% | "
                   f"{d['sepakat_band']}/{r['n_kasus']} ({d['sepakat_persen']}%) |")

    esk = r["eskalasi"]
    kep = r["kepekaan_harga"]
    out += [
        "",
        "## Eskalasi",
        "",
        f"{esk['total']} eskalasi terjadi; {esk['mengubah_band']} di antaranya mengubah band "
        f"({esk['presisi_persen']}%)." if esk["total"] else
        "Tidak ada eskalasi pada sampel ini.",
        "",
        "## Kepekaan harga [AD-7]",
        "",
        f"Perencana memilih probe berbeda pada **{kep['kasus_pilihan_berbeda']} dari "
        f"{r['n_kasus']} kasus** ({kep['persen']}%) ketika harga kredit disembunyikan "
        "dari katalognya.",
        "",
        ("Angka ini yang memberi isi pada klaim *pemilihan tool sadar biaya*. "
         "Kalau ia nol, klaim itu harus dicabut dari video dan dari README."
         if kep["kasus_pilihan_berbeda"] == 0 else
         "Perencana benar-benar membaca harga saat memilih, bukan sekadar diberi tahu."),
        "",
        f"Perencana LLM berhasil pada {r['perencana_llm']}/{r['n_kasus']} kasus; sisanya "
        "memakai rencana cadangan berbasis aturan dan **tidak boleh dihitung sebagai bukti "
        "kecerdasan agen**.",
        "",
        "## Per emiten",
        "",
        "| Emiten | Agen | Menyeluruh | Band agen | Band acuan | Probe yang dipilih agen |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for b in baris:
        a, m = b.per_lengan["agen"], b.per_lengan["menyeluruh"]
        tanda = "" if a.band == m.band else " ⚠️"
        out.append(f"| {b.symbol} | {a.credits} | {m.credits} | {a.band}{tanda} | {m.band} | "
                   f"{', '.join(a.probes_run) or '—'} |")

    out += [
        "",
        "## Batasan",
        "",
        f"- **{r['n_kasus']} emiten**, di bawah sasaran 30–50. Warehouse baru memuat "
        "sebanyak ini; lihat `evals/cases.yaml`.",
        "- Satu tanggal acuan, bukan rentang. Hasilnya tidak menunjukkan kestabilan "
        "antar-waktu.",
        "- Lengan menyeluruh dipakai sebagai acuan band, padahal ia sendiri tidak "
        "terkalibrasi penuh: FFS dan BCI berbobot prior domain "
        "(`contracts/CHANGES.md` C5). Kesepakatan band mengukur konsistensi terhadap "
        "penyelidikan lengkap, **bukan** ketepatan terhadap kebenaran pasar.",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Eval agen — Angka 2")
    ap.add_argument("--offline", action="store_true", help="FakeLLM, nol jaringan")
    ap.add_argument("--tulis", action="store_true", help="tulis reports/agent-eval.md")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 11))
    args = ap.parse_args(argv)

    kasus = muat()
    if args.limit:
        kasus = kasus[: args.limit]
    print(f"{len(kasus)} kasus, acuan {args.as_of}"
          f"{' (offline)' if args.offline else ''}")

    baris = jalankan(kasus, as_of=args.as_of, offline=args.offline)
    r = ringkas(baris, args.as_of)

    HASIL.mkdir(parents=True, exist_ok=True)
    (HASIL / f"{args.as_of.isoformat()}.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    L = r["lengan"]
    print(f"\n  agen          {L['agen']['kredit_rata2']:5} kredit  "
          f"hemat {L['agen']['hemat_persen']}%  sepakat {L['agen']['sepakat_persen']}%")
    print(f"  urutan tetap  {L['urutan_tetap']['kredit_rata2']:5} kredit  "
          f"sepakat {L['urutan_tetap']['sepakat_persen']}%")
    print(f"  acak          {L['acak']['kredit_rata2']:5} kredit  "
          f"sepakat {L['acak']['sepakat_persen']}%")
    print(f"  kepekaan harga: {r['kepekaan_harga']['kasus_pilihan_berbeda']}/"
          f"{r['n_kasus']} kasus berbeda pilihan")

    if args.tulis:
        LAPORAN.parent.mkdir(parents=True, exist_ok=True)
        LAPORAN.write_text(render(r, baris), encoding="utf-8")
        print(f"\ntulis {LAPORAN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
