# reports/agent-eval-portofolio.md — alokasi adaptif

_16 emiten, acuan 2026-09-11, pagu total **102 kredit**. Dibangkitkan `python3 evals/portfolio.py --tulis`._

Eval ini menguji apa yang eval per-emiten tidak bisa uji: **apakah agen membagi pagu lebih baik daripada pembagian rata.** Alasannya di docstring `evals/portfolio.py` — pada pagu tetap per emiten, pemilihan probe adalah knapsack dan punya jawaban optimal tanpa LLM.

| Lengan | Kredit total | Sepakat band |
| --- | --- | --- |
| **Agen (alokasi bebas)** | 102 | 11/16 (68.8%) |
| Urutan tetap, pagu dibagi rata | 92 | 13/16 (81.2%) |
| Oracle knapsack, pagu dibagi rata | 92 | 13/16 (81.2%) |
| Oracle memakai alokasi agen | 102 | 11/16 (68.8%) |
| Menyeluruh (acuan) | 256 | 16/16 (100.0%) |

## Cara membacanya

- **Agen vs rata** — inti klaim alokasi adaptif. Agen 68.8% melawan 81.2% (oracle rata).
- **Oracle memakai alokasi agen** (68.8%) memisahkan dua pertanyaan: kalau lengan ini mengalahkan agen, alokasinya bagus tapi pemilihan probenya yang kurang; kalau ia mengalahkan oracle-rata, alokasi agen memang bernilai terlepas dari pilihan probenya.

## Sebaran alokasi agen

Terendah 1, median 7, tertinggi 16 kredit; pembagian rata memberi 6 untuk semua.

Sebaran alokasinya lebar — agen benar-benar membedakan emiten yang layak diselidiki dalam daripada yang tidak.
