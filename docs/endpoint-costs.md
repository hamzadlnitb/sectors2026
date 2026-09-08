<!-- DIBANGKITKAN oleh tools/gen_docs.py — jangan diedit tangan. Ubah core/sectors/routing.py lalu jalankan: make docs -->

# Biaya kredit per endpoint Sectors

Sumber kebenaran: [`core/sectors/routing.py`](../core/sectors/routing.py). Perencana agen menganggarkan dari angka di tabel ini, jadi angka yang salah di sini berarti pagu investigasi yang salah.

> 7 dari 15 endpoint sudah diukur lewat `make spike` (`spikes/observed.json`, 2026-09-08T10:20:40+00:00). Sisanya masih **asumsi** — lihat kolom *Status*.

## Tier 1 — sapuan market-wide harian

Dijalankan cron tiap hari bursa. Total **5 kredit/hari** (target ≤6 — dijaga `tests/sectors/test_routing.py`).

| Endpoint | Kredit | Status | Transport | Cadangan | Untuk apa |
| --- | ---: | --- | --- | --- | --- |
| `fetch-close` | 1 | asumsi | rest | mcp | Harga penutupan seluruh ticker IDX untuk satu tanggal bursa. |
| `fetch-companies-top-changes` | 1 | terukur | rest | mcp | Emiten dengan perubahan harga/volume terbesar pada satu periode. |
| `fetch-filings` | 1 | terukur | rest | mcp | Filing transaksi insider (pemegang saham & pengurus). |
| `fetch-most-traded-stocks` | 1 | terukur | rest | mcp | Saham paling banyak diperdagangkan pada rentang tanggal. |
| `fetch-suspensions` | 1 | terukur | rest | mcp | Riwayat suspensi IDX beserta alasan resminya. Sumber label kalibrasi. |

## Tier 2 — hanya lewat probe agen

Tidak pernah dipanggil terjadwal. Hanya keluar saat agen memutuskan satu probe layak dibeli untuk satu saham.

| Endpoint | Kredit | Status | Transport | Cadangan | Untuk apa |
| --- | ---: | --- | --- | --- | --- |
| `fetch-broker-summary` | 2 | asumsi | mcp | — | Rincian net buy/sell per kode broker untuk satu ticker. |
| `fetch-broker-summary-top` | 3 | asumsi | rest | mcp | Broker dengan net buy/sell terbesar pada satu ticker dan rentang tanggal. |
| `fetch-companies-by-subsector` | 1 | asumsi | mcp | — | Daftar emiten dalam satu subsektor. Dipakai membentuk himpunan kontrol tersamakan saat kalibrasi. |
| `fetch-company-report` | 2 | terukur | rest | mcp | Profil emiten: subsektor, kapitalisasi, tanggal listing, ikhtisar keuangan. |
| `fetch-corporate-actions` | 2 | asumsi | mcp | — | Aksi korporasi: rights issue, stock split, dividen, private placement. |
| `fetch-daily-transaction` | 1 | terukur | rest | mcp | Harga, volume, dan kapitalisasi harian satu ticker pada rentang tanggal. |
| `fetch-foreign-flow` | 2 | terukur | rest | mcp | Arus dana asing bersih harian pada satu ticker. |
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

## Temuan spike F0

Spike 8 Sep memanggil 12 endpoint sekali masing-masing (9 kredit). Respons mentahnya di [`spikes/raw/`](../spikes/raw) dan di-commit — seluruh lapisan parsing bisa diuji ulang selamanya tanpa jaringan lewat `tests/sectors/test_respons_asli.py`.

**7 endpoint menjawab benar** dan biayanya terukur. Bentuk responsnya ternyata **tidak seragam** — ada empat bentuk berbeda (daftar rata, `{results, pagination}`, pembungkus bercontext + `data`, dan dict berkunci tanggal). Adapter per endpoint ada di `core/sectors/schemas.py`.

**5 endpoint GAGAL.** Ini yang harus dibereskan sebelum jalurnya dipakai:

| Endpoint | Sebab saat spike |
| --- | --- |
| `fetch-broker-summary-top` | 'fetch-broker-summary-top' gagal setelah 2 percobaan: SDK mcp tidak terpasang (cannot import name 'streamablehttp_client' from 'mcp.client.streamable_… |
| `fetch-close` | 'fetch-close' gagal setelah 2 percobaan: SDK mcp tidak terpasang (cannot import name 'streamablehttp_client' from 'mcp.client.streamable_http' (<jalur… |
| `fetch-corporate-actions` | 'fetch-corporate-actions' gagal setelah 1 percobaan: SDK mcp tidak terpasang (cannot import name 'streamablehttp_client' from 'mcp.client.streamable_h… |
| `fetch-free-float` | 'fetch-free-float' gagal setelah 1 percobaan: SDK mcp tidak terpasang (cannot import name 'streamablehttp_client' from 'mcp.client.streamable_http' (<… |
| `fetch-quarterly-financials` | 'fetch-quarterly-financials' gagal setelah 1 percobaan: SDK mcp tidak terpasang (cannot import name 'streamablehttp_client' from 'mcp.client.streamabl… |

Sebab **SDK mcp** di atas sudah diperbaiki setelah spike: nama fungsinya `streamable_http_client`, bukan `streamablehttp_client`, dan header otorisasi harus lewat klien httpx yang sudah dikonfigurasi. Dikunci `tests/sectors/test_transport_mcp.py`. Endpoint yang gagal **hanya karena itu** kemungkinan besar hidup, tapi belum dibuktikan — perlu spike ulang.

Yang gagal karena **HTTP**, bukan karena SDK, memang jalurnya salah dan belum bisa disimpulkan dari data yang ada: `fetch-close` menjawab `400 Invalid query parameters: date` (jalurnya ada, paramnya salah) dan `fetch-broker-summary-top` menjawab `404` (jalurnya tidak ada). Keduanya butuh spike lanjutan, perkiraan ±4 kredit.

> ⚠️ **Paginasi.** `fetch-suspensions` melaporkan `total_count: 533` tapi hanya mengirim **20 baris per panggilan**; `fetch-filings` 223 dari 20. Backfill yang mengabaikan `limit`/`offset` akan mengira sudah menarik 24 bulan padahal baru satu halaman — dan himpunan positif kalibrasi jadi sepotong. Anggaran tahap 2 di `core/ingest/backfill.py` **belum** memperhitungkan halaman tambahan.

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
