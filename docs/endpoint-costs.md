<!-- DIBANGKITKAN oleh tools/gen_docs.py — jangan diedit tangan. Ubah core/sectors/routing.py lalu jalankan: make docs -->

# Biaya kredit per endpoint Sectors

Sumber kebenaran: [`core/sectors/routing.py`](../core/sectors/routing.py). Perencana agen menganggarkan dari angka di tabel ini, jadi angka yang salah di sini berarti pagu investigasi yang salah.

> ⚠️ **Belum ada satu pun biaya yang terukur.** Seluruh kolom *kredit* di bawah masih **asumsi**. Jalankan `make spike` (butuh `SECTORS_API_KEY`) untuk mengukurnya; hasilnya masuk ke `spikes/observed.json` dan otomatis menimpa asumsi di sini. Jangan menganggarkan ketat di atas angka yang belum terukur.

## Tier 1 — sapuan market-wide harian

Dijalankan cron tiap hari bursa. Total **5 kredit/hari** (target ≤6 — dijaga `tests/sectors/test_routing.py`).

| Endpoint | Kredit | Status | Transport | Cadangan | Untuk apa |
| --- | ---: | --- | --- | --- | --- |
| `fetch-close` | 1 | asumsi | rest | mcp | Harga penutupan seluruh ticker IDX untuk satu tanggal bursa. |
| `fetch-companies-top-changes` | 1 | asumsi | rest | mcp | Emiten dengan perubahan harga/volume terbesar pada satu periode. |
| `fetch-filings` | 1 | asumsi | rest | mcp | Filing transaksi insider (pemegang saham & pengurus). |
| `fetch-most-traded-stocks` | 1 | asumsi | rest | mcp | Saham paling banyak diperdagangkan pada rentang tanggal. |
| `fetch-suspensions` | 1 | asumsi | rest | mcp | Riwayat suspensi IDX beserta alasan resminya. Sumber label kalibrasi. |

## Tier 2 — hanya lewat probe agen

Tidak pernah dipanggil terjadwal. Hanya keluar saat agen memutuskan satu probe layak dibeli untuk satu saham.

| Endpoint | Kredit | Status | Transport | Cadangan | Untuk apa |
| --- | ---: | --- | --- | --- | --- |
| `fetch-broker-summary` | 2 | asumsi | mcp | — | Rincian net buy/sell per kode broker untuk satu ticker. |
| `fetch-broker-summary-top` | 3 | asumsi | rest | mcp | Broker dengan net buy/sell terbesar pada satu ticker dan rentang tanggal. |
| `fetch-companies-by-subsector` | 1 | asumsi | mcp | — | Daftar emiten dalam satu subsektor. Dipakai membentuk himpunan kontrol tersamakan saat kalibrasi. |
| `fetch-company-report` | 2 | asumsi | rest | mcp | Profil emiten: subsektor, kapitalisasi, tanggal listing, ikhtisar keuangan. |
| `fetch-corporate-actions` | 2 | asumsi | mcp | — | Aksi korporasi: rights issue, stock split, dividen, private placement. |
| `fetch-daily-transaction` | 1 | asumsi | rest | mcp | Harga, volume, dan kapitalisasi harian satu ticker pada rentang tanggal. |
| `fetch-foreign-flow` | 2 | asumsi | rest | mcp | Arus dana asing bersih harian pada satu ticker. |
| `fetch-free-float` | 1 | asumsi | mcp | — | Persentase saham beredar bebas (free float) per emiten. |
| `fetch-quarterly-financials` | 2 | asumsi | mcp | — | Laporan keuangan kuartalan: pendapatan, laba bersih, total aset. |
| `fetch-shareholders-composition` | 2 | asumsi | mcp | — | Komposisi pemegang saham dan porsi kepemilikan asing. |

## Biaya per probe

Yang dilihat perencana. Biaya probe = jumlah biaya endpoint yang dibungkusnya, dihitung dari tabel di atas — bukan ditulis terpisah.

| Probe | Komponen | Kredit | Transport | Endpoint |
| --- | --- | ---: | --- | --- |
| `probe_volume_anomaly` | VAS | 1 | rest | `fetch-daily-transaction` |
| `probe_free_float` | FFS | 1 | mcp | `fetch-free-float` |
| `probe_price_fundamental` | PFD | 3 | mcp+rest | `fetch-close`, `fetch-quarterly-financials` |
| `probe_foreign_flow` | FRD | 3 | rest | `fetch-foreign-flow`, `fetch-daily-transaction` |
| `probe_structural` | SSS | 4 | mcp+rest | `fetch-suspensions`, `fetch-filings`, `fetch-corporate-actions` |
| `probe_broker_concentration` | BCI | 5 | mcp+rest | `fetch-broker-summary-top`, `fetch-broker-summary` |

**Investigasi menyeluruh = 17 kredit** — ini penyebut klaim penghematan agen (Angka 2, `ARCHITECTURE.md` §6), dan harus tetap di bawah pagar 25 kredit per investigasi `[AD-6]`.

## Anggaran fase

Ditegakkan `CreditAwareClient`: panggilan yang menembus pagu **ditolak** dengan `BudgetExceeded`, bukan diperingatkan. `make credits` mencetak posisi terkini dari `data/credit_ledger.jsonl`.

| Fase | Pagu |
| --- | ---: |
| Spike + pengembangan probe (`dev`) | 120 |
| Backfill + kalibrasi (`backfill`) | 400 |
| Eval agen (`eval`) | 130 |
| Operasi harian (`daily`) | 250 |
| Cadangan (`reserve`) | 100 |
| **Total** | **1000** |

---
_Dibangkitkan 2026-09-08 oleh `make docs`._
