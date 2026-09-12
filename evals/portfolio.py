"""Eval portofolio — satu pagu total untuk seluruh emiten.

## Kenapa eval ini ada

Eval per-emiten (`agent_eval.py`) memberi tiap lengan pagu yang sama untuk tiap
emiten, lalu mengukur kesepakatan band. Ternyata itu mengukur masalah yang sudah
selesai: pada pagu tetap, memilih probe supaya cakupan bobot maksimum adalah
**knapsack**, dan `arms.himpunan_optimal()` menyelesaikannya secara pasti tanpa LLM.
Di ruang itu agen hanya bisa menyamai atau kalah.

Yang knapsack **tidak bisa** lakukan adalah memutuskan berapa pagu yang pantas untuk
satu emiten. Ia harus diberi pagu. Agen yang menentukannya — dan itu persis klaim
kami di ARCHITECTURE §1: *"memutuskan bukti mana yang layak dibeli untuk emiten ini,
hari ini."*

Eval per-emiten menghapus kemampuan itu dari pengukuran, karena memaksa setiap emiten
mendapat jatah yang sama. Eval ini mengembalikannya: **satu pagu total, bebas
dialokasikan.**

## Aturan main

Pagu total = yang benar-benar dipakai agen pada seluruh emiten. Lengan pembanding
mendapat total yang sama, dibagi **rata** — karena tanpa agen, tidak ada dasar untuk
membaginya tidak rata. Itulah keunggulan yang sedang diuji.

Kalau agen tidak mengalahkan pembagian rata di sini juga, klaim alokasi adaptif tidak
punya isi dan harus dicabut, bukan dihaluskan.

    python3 evals/portfolio.py --offline
    python3 evals/portfolio.py --tulis
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ingest.warehouse import Warehouse  # noqa: E402
from core.probes.base import Context  # noqa: E402
from evals import arms  # noqa: E402
from evals.build_cases import muat  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LAPORAN = ROOT / "reports" / "agent-eval-portofolio.md"
HASIL = ROOT / "runs" / "evals"


@dataclass
class Portofolio:
    nama: str
    per_emiten: dict[str, arms.ArmResult] = field(default_factory=dict)

    @property
    def kredit(self) -> int:
        return sum(a.credits for a in self.per_emiten.values())

    def sepakat(self, acuan: dict[str, str]) -> int:
        return sum(1 for s, a in self.per_emiten.items() if a.band == acuan[s])


def _ctx(as_of: date) -> Context:
    return Context(as_of=as_of, warehouse=Warehouse(), client=None, phase="eval")


def jalankan(kasus: list[dict], *, as_of: date, offline: bool) -> dict:
    if offline:
        from core.llm import FakeLLM
        llm = FakeLLM()
    else:
        from core.llm import LLM
        llm = LLM.from_env(eval_mode=True)

    simbol = [k["symbol"] for k in kasus]

    acuan_arm = {s: arms.menyeluruh(s, _ctx(as_of)) for s in simbol}
    acuan = {s: a.band for s, a in acuan_arm.items()}

    agen = Portofolio("agen")
    from evals.agent_eval import PEKERJA

    def _agen(s: str):
        hasil = arms.agen(s, _ctx(as_of), llm, as_of=as_of)
        print(f"  {s}  agen {hasil.credits:2d} kredit", flush=True)
        return s, hasil

    with ThreadPoolExecutor(max_workers=max(1, PEKERJA)) as pool:
        for s, hasil in pool.map(_agen, simbol):
            agen.per_emiten[s] = hasil

    total = agen.kredit
    # Pembagian rata: sisa dibagi ke emiten pertama supaya total benar-benar sama,
    # bukan dibulatkan ke bawah dan diam-diam memberi agen pagu lebih besar.
    dasar, sisa = divmod(total, len(simbol))
    jatah = {s: dasar + (1 if i < sisa else 0) for i, s in enumerate(simbol)}

    rata_tetap = Portofolio("rata_urutan_tetap")
    rata_oracle = Portofolio("rata_oracle")
    for s in simbol:
        rata_tetap.per_emiten[s] = arms.urutan_tetap(s, _ctx(as_of), jatah[s])
        rata_oracle.per_emiten[s] = arms.oracle(s, _ctx(as_of), jatah[s])

    # Oracle yang diberi pagu PERSIS seperti alokasi agen: memisahkan dua
    # pertanyaan berbeda — apakah alokasinya bagus, dan apakah pemilihannya bagus.
    oracle_alokasi_agen = Portofolio("oracle_pakai_alokasi_agen")
    for s in simbol:
        oracle_alokasi_agen.per_emiten[s] = arms.oracle(
            s, _ctx(as_of), agen.per_emiten[s].credits)

    menyeluruh = Portofolio("menyeluruh")
    menyeluruh.per_emiten = acuan_arm

    lengan = [agen, rata_tetap, rata_oracle, oracle_alokasi_agen, menyeluruh]
    n = len(simbol)
    return {
        "as_of": as_of.isoformat(),
        "n_kasus": n,
        "pagu_total": total,
        "jatah_rata": dasar,
        "alokasi_agen": {s: agen.per_emiten[s].credits for s in simbol},
        "lengan": {
            p.nama: {
                "kredit_total": p.kredit,
                "sepakat": p.sepakat(acuan),
                "sepakat_persen": round(100 * p.sepakat(acuan) / n, 1),
            }
            for p in lengan
        },
    }


def render(r: dict) -> str:
    L = r["lengan"]
    alok = sorted(r["alokasi_agen"].values())
    out = [
        "# reports/agent-eval-portofolio.md — alokasi adaptif",
        "",
        f"_{r['n_kasus']} emiten, acuan {r['as_of']}, pagu total "
        f"**{r['pagu_total']} kredit**. Dibangkitkan `python3 evals/portfolio.py --tulis`._",
        "",
        "Eval ini menguji apa yang eval per-emiten tidak bisa uji: **apakah agen membagi "
        "pagu lebih baik daripada pembagian rata.** Alasannya di docstring "
        "`evals/portfolio.py` — pada pagu tetap per emiten, pemilihan probe adalah "
        "knapsack dan punya jawaban optimal tanpa LLM.",
        "",
        "| Lengan | Kredit total | Sepakat band |",
        "| --- | --- | --- |",
    ]
    label = {
        "agen": "**Agen (alokasi bebas)**",
        "rata_urutan_tetap": "Urutan tetap, pagu dibagi rata",
        "rata_oracle": "Oracle knapsack, pagu dibagi rata",
        "oracle_pakai_alokasi_agen": "Oracle memakai alokasi agen",
        "menyeluruh": "Menyeluruh (acuan)",
    }
    for k in ("agen", "rata_urutan_tetap", "rata_oracle", "oracle_pakai_alokasi_agen",
              "menyeluruh"):
        d = L[k]
        out.append(f"| {label[k]} | {d['kredit_total']} | {d['sepakat']}/{r['n_kasus']} "
                   f"({d['sepakat_persen']}%) |")

    out += [
        "",
        "## Cara membacanya",
        "",
        f"- **Agen vs rata** — inti klaim alokasi adaptif. Agen {L['agen']['sepakat_persen']}% "
        f"melawan {L['rata_oracle']['sepakat_persen']}% (oracle rata).",
        f"- **Oracle memakai alokasi agen** ({L['oracle_pakai_alokasi_agen']['sepakat_persen']}%) "
        "memisahkan dua pertanyaan: kalau lengan ini mengalahkan agen, alokasinya bagus "
        "tapi pemilihan probenya yang kurang; kalau ia mengalahkan oracle-rata, alokasi "
        "agen memang bernilai terlepas dari pilihan probenya.",
        "",
        "## Sebaran alokasi agen",
        "",
        f"Terendah {alok[0]}, median {alok[len(alok) // 2]}, tertinggi {alok[-1]} kredit; "
        f"pembagian rata memberi {r['jatah_rata']} untuk semua.",
        "",
        ("⚠️ **Agen membagi nyaris rata.** Kalau sebarannya sempit, alokasi adaptif tidak "
         "benar-benar terjadi dan klaimnya harus dicabut, bukan dihaluskan."
         if alok[-1] - alok[0] <= 2 else
         "Sebaran alokasinya lebar — agen benar-benar membedakan emiten yang layak "
         "diselidiki dalam daripada yang tidak."),
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Eval portofolio — alokasi adaptif")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--tulis", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 11))
    args = ap.parse_args(argv)

    kasus = muat()
    if args.limit:
        kasus = kasus[: args.limit]
    print(f"{len(kasus)} emiten, acuan {args.as_of}"
          f"{' (offline)' if args.offline else ''}")

    r = jalankan(kasus, as_of=args.as_of, offline=args.offline)

    HASIL.mkdir(parents=True, exist_ok=True)
    (HASIL / f"portofolio-{args.as_of.isoformat()}.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n  pagu total {r['pagu_total']} kredit ({r['jatah_rata']}/emiten kalau rata)")
    for k, d in r["lengan"].items():
        print(f"  {k:28s} {d['kredit_total']:4d} kredit  sepakat {d['sepakat_persen']:5}%")

    if args.tulis:
        LAPORAN.parent.mkdir(parents=True, exist_ok=True)
        LAPORAN.write_text(render(r), encoding="utf-8")
        print(f"\ntulis {LAPORAN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
