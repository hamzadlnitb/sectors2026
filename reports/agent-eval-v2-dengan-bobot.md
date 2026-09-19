# reports/agent-eval.md — Angka 2

_16 emiten, tanggal acuan 2026-09-11. Dibangkitkan `python3 evals/agent_eval.py --tulis`._

Satuan biaya adalah **kredit terhitung** — jumlah `cost_estimate()` probe yang dijalankan, yaitu biaya seandainya warehouse kosong. Eval berjalan dengan `client=None` sehingga nol kredit benar-benar terbakar. Alasannya di docstring `evals/arms.py`: kredit terbakar mengukur keberuntungan cache, bukan kualitas perencanaan.

## Hasil

| Lengan | Kredit rata-rata | Hemat vs menyeluruh | Sepakat band |
| --- | --- | --- | --- |
| Menyeluruh (acuan) | 16 | 0.0% | 16/16 (100.0%) |
| **Agen** | 6.38 | 60.2% | 11/16 (68.8%) |
| Urutan tetap | 6.38 | 60.2% | 11/16 (68.8%) |
| Acak berpagu sama | 6.31 | 60.5% | 11/16 (68.8%) |
| Agen tanpa lihat harga | 5.88 | 63.3% | 12/16 (75.0%) |

## Eskalasi

Tidak ada eskalasi pada sampel ini.

## Kepekaan harga [AD-7]

Perencana memilih probe berbeda pada **16 dari 16 kasus** (100.0%) ketika harga kredit disembunyikan dari katalognya.

Perencana benar-benar membaca harga saat memilih, bukan sekadar diberi tahu.

Perencana LLM berhasil pada 15/16 kasus; sisanya memakai rencana cadangan berbasis aturan dan **tidak boleh dihitung sebagai bukti kecerdasan agen**.

## Per emiten

| Emiten | Agen | Menyeluruh | Band agen | Band acuan | Probe yang dipilih agen |
| --- | --- | --- | --- | --- | --- |
| ASLI | 7 | 16 | perhatian | perhatian | free_float, volume_anomaly, foreign_flow, broker_concentration |
| CSMI | 7 | 16 | normal | normal | volume_anomaly, broker_concentration, free_float, foreign_flow |
| LIFE | 7 | 16 | perhatian | perhatian | volume_anomaly, free_float, broker_concentration, foreign_flow |
| NICK | 5 | 16 | waspada | waspada | free_float, volume_anomaly, broker_concentration |
| PACK | 7 | 16 | normal | normal | volume_anomaly, free_float, foreign_flow, broker_concentration |
| PPGL | 11 | 16 | perhatian ⚠️ | normal | volume_anomaly, free_float, broker_concentration, price_fundamental |
| SAFE | 10 | 16 | perhatian | perhatian | volume_anomaly, free_float, broker_concentration, structural, foreign_flow |
| TRUK | 10 | 16 | perhatian | perhatian | volume_anomaly, broker_concentration, free_float, foreign_flow, structural |
| ARNA | 7 | 16 | normal | normal | volume_anomaly, free_float, foreign_flow, broker_concentration |
| CGAS | 2 | 16 | perhatian | perhatian | volume_anomaly, free_float |
| CTTH | 5 | 16 | perhatian ⚠️ | normal | volume_anomaly, free_float, broker_concentration |
| INOV | 1 | 16 | normal ⚠️ | perhatian | volume_anomaly |
| JAWA | 5 | 16 | perhatian | perhatian | volume_anomaly, free_float, broker_concentration |
| KLBF | 7 | 16 | perhatian ⚠️ | normal | foreign_flow, broker_concentration, volume_anomaly, free_float |
| MSKY | 7 | 16 | perhatian | perhatian | volume_anomaly, free_float, foreign_flow, broker_concentration |
| SCCO | 4 | 16 | waspada ⚠️ | perhatian | volume_anomaly, free_float, foreign_flow |

## Batasan

- **16 emiten**, di bawah sasaran 30–50. Warehouse baru memuat sebanyak ini; lihat `evals/cases.yaml`.
- Satu tanggal acuan, bukan rentang. Hasilnya tidak menunjukkan kestabilan antar-waktu.
- Lengan menyeluruh dipakai sebagai acuan band, padahal ia sendiri tidak terkalibrasi penuh: FFS dan BCI berbobot prior domain (`contracts/CHANGES.md` C5). Kesepakatan band mengukur konsistensi terhadap penyelidikan lengkap, **bukan** ketepatan terhadap kebenaran pasar.
