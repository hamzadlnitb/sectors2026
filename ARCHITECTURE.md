# ARCHITECTURE.md — PANTAU

> **PANTAU** — sistem peringatan dini risiko manipulasi & likuiditas untuk saham IDX.
> Sectors Hackathon 2026 · **Track 3 — Market Intelligence**

Semua keputusan di dokumen ini punya jejak ke `RESEARCH.md`. Nomor taktik `[Tn]` merujuk ke bagian 3 dokumen tersebut.

---

## 1. Ringkasan Produk

### Problem statement (1 kalimat, untuk form submission)
> Untuk investor ritel IDX yang menerima rekomendasi saham dari grup Telegram dan TikTok, PANTAU menjawab satu pertanyaan yang tidak bisa dijawab aplikasi sekuritas mana pun: *"saham ini lagi ramai — ini nyata atau digoreng?"*

### Persona (satu, tidak lebih) `[T1]`
**Rina, 26 tahun, Bekasi.** Bagian dari 54,12% investor IDX di bawah 30 tahun. Modal Rp 20 juta di aplikasi sekuritas. Dapat ticker dari grup Telegram. Tidak tahu cara baca broker summary, tidak tahu apa itu free float, tidak tahu saham itu sedang di Papan Pemantauan Khusus. Yang dia butuhkan bukan rekomendasi beli — dia butuh **tahu kalau dia sedang jadi exit liquidity.**

### Bentuk produk
1. **Halaman Ticker** — masukkan kode saham → **Skor PANTAU 0–100** + 6 sub-skor risiko + narasi Bahasa Indonesia. Setiap angka di narasi bisa diklik balik ke endpoint Sectors + timestamp `as-of`. `[T12]`
2. **Papan Waspada** — daftar harian saham yang skornya naik tajam, dihasilkan pipeline terjadwal tanpa campur tangan manusia. Terarsip per tanggal di repo. `[T5]`
3. **Halaman Metodologi** — rumus tiap komponen, bobot, hasil kalibrasi, dan hasil backtest dipublikasikan terbuka. Ini yang membedakan alat analisis dari dukun. `[T6][T7]`

### Kenapa ini, bukan yang lain
| Alasan | Bukti |
| --- | --- |
| Framing **perlindungan investor**, bukan saran finansial → aman terhadap larangan rules | `RESEARCH.md` §1 aturan keras, `[T13]` |
| Bersandar pada data yang **cuma Sectors punya** (broker summary, foreign flow, free float, suspensi, filings) → skor inovasi API tinggi | `[T3]` |
| **Tidak ada** di pustaka recipe resmi Sectors → tidak menyerahkan tutorial juri ke jurinya sendiri | `[T4]` |
| Ada **label alami** (`fetch-suspensions`) → bisa dikalibrasi & di-backtest → menghasilkan satu angka terukur | `[T6]` |
| Relevan dengan debat **Papan Pemantauan Khusus / FCA** yang sedang berjalan di OJK–IDX–Komisi XI | `[T13]` |
| Menghasilkan **derived insight**, bukan visualisasi ulang data mentah → lolos tes wajib Track 3 | `RESEARCH.md` §1 tabel track |

### Uji "cabut Sectors" (gerbang eligibility)
Cabut Sectors → tidak ada broker summary, tidak ada foreign flow, tidak ada free float, tidak ada riwayat suspensi. Keenam komponen skor mati. **Produk tinggal cangkang kosong.** Lolos.

---

## 2. Kendala yang Menyetir Arsitektur

| # | Kendala | Implikasi arsitektur |
| --- | --- | --- |
| K1 | **1.000 kredit API total**, biaya 1–3 kredit/panggilan | Mustahil query live per request. Wajib ingestion batch + snapshot lokal + **ledger kredit yang ditegakkan di kode** |
| K2 | Penjurian **asinkron**, tanpa pitch live | Jalur demo harus mustahil gagal. Semua yang tampil di video sudah terprakomputasi `[T9]` |
| K3 | **Freeze total** saat submit, tanpa bug fix | Feature freeze internal H-4. Buffer submit 24 jam `[T15]` |
| K4 | Repo **diverifikasi juri** | README, diagram, tabel endpoint, one-command run, tes, commit history rapi `[T7]` |
| K5 | Dilarang saran finansial | Tidak ada kata "beli/jual/target harga" di seluruh output. Disclaimer permanen di UI |
| K6 | Dilarang eksekusi order | Nol integrasi broker. Nol kode order |
| K7 | Data Sectors EOD (bukan realtime) | Produk dibingkai sebagai **peringatan harian pasca-tutup**, bukan alat intraday. Jujur soal keterlambatan data |

### K1 dijadikan senjata, bukan beban
Anggaran kredit yang ketat memaksa desain **ingestion dua tingkat** yang justru jadi bahan cerita teknis paling kuat di video: *"kami memantau seluruh bursa dengan 12 kredit per hari."* `[T6]`

---

## 3. Enam Komponen Skor PANTAU

Skor komposit dihitung dari enam sub-skor independen, masing-masing dinormalisasi ke 0–100. Semuanya **deterministik dan murni fungsional** — tidak ada LLM di jalur perhitungan.

| Kode | Komponen | Pertanyaan yang dijawab | Sumber data Sectors |
| --- | --- | --- | --- |
| **BCI** | Broker Concentration Index | Berapa persen net buy dikuasai 3 broker teratas? (HHI) | `fetch-broker-summary-top`, `fetch-broker-summary` |
| **VAS** | Volume Anomaly Score | Volume hari ini berapa sigma di atas baseline 90 hari? | `fetch-daily-transaction`, `fetch-most-traded-stocks` |
| **PFD** | Price–Fundamental Divergence | Harga naik 200% sementara laba flat/rugi? | `fetch-company-report`, `fetch-quarterly-financials`, `fetch-close` |
| **FFS** | Free Float Scarcity | Berapa kecil saham yang benar-benar beredar? | `fetch-free-float`, `fetch-company-report` |
| **FRD** | Foreign–Retail Divergence | Asing keluar sementara harga naik = distribusi ke ritel? | `fetch-foreign-flow`, `fetch-shareholders-composition` |
| **SSS** | Structural Signal Score | Pernah disuspend? Insider jual saat harga naik? Rights issue beruntun? | `fetch-suspensions`, `fetch-filings`, `fetch-corporate-actions` |

```
PANTAU = Σ (wᵢ · sub_skorᵢ),  Σwᵢ = 1
```

Bobot `wᵢ` **tidak ditebak** — dikalibrasi pada peristiwa historis berlabel (lihat §5). Bobot final dan proses kalibrasinya dipublikasikan di halaman Metodologi. `[T6]`

### Band interpretasi
| Skor | Band | Bahasa yang dipakai di UI |
| --- | --- | --- |
| 0–29 | Normal | "Tidak ada pola tidak biasa terdeteksi" |
| 30–59 | Perlu diperhatikan | "Ada beberapa pola yang layak dicermati" |
| 60–79 | Waspada | "Beberapa indikator menunjukkan pola tidak biasa" |
| 80–100 | Sangat waspada | "Banyak indikator menunjukkan pola tidak biasa secara bersamaan" |

Tidak ada band yang berbunyi "jual" atau "hindari". `[K5]`

---

## 4. Arsitektur Sistem

```
┌──────────────────────────────────────────────────────────────────┐
│  SECTORS API v2  +  SECTORS MCP                                  │
└───────────────────────────┬──────────────────────────────────────┘
                            │  satu-satunya pintu keluar jaringan
                ┌───────────▼────────────┐
                │  CreditAwareClient     │  ledger kredit, rate limit,
                │  (core/sectors/)       │  retry, cache disk permanen
                └───────────┬────────────┘
                            │
        ┌───────────────────▼────────────────────┐
        │  INGESTION 2 TINGKAT                   │
        │                                        │
        │  Tier 1 — market-wide, ±6 kredit/hari  │
        │    fetch-close (1 call = semua ticker) │
        │    fetch-most-traded-stocks            │
        │    fetch-companies-top-changes         │
        │    fetch-suspensions                   │
        │    fetch-filings                       │
        │            │                           │
        │            ▼  prefilter kandidat       │
        │  Tier 2 — per-ticker, top 10–15 saja   │
        │    fetch-broker-summary-top            │
        │    fetch-foreign-flow                  │
        │    fetch-daily-transaction             │
        │    fetch-company-report                │
        └───────────────────┬────────────────────┘
                            ▼
                ┌────────────────────────┐
                │  SNAPSHOT STORE        │  DuckDB + Parquet
                │  (data/warehouse/)     │  di-commit ke repo
                └───────────┬────────────┘
                            ▼
                ┌────────────────────────┐
                │  SCORING ENGINE        │  Python murni, deterministik
                │  (core/scoring/)       │  6 komponen → skor + fact table
                └───────────┬────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
   ┌────────────────────┐      ┌──────────────────────┐
   │ NARRATIVE LAYER    │      │  EXPORTER            │
   │ LLM, cite-before-  │      │  → public/data/*.json│
   │ act, output di-    │      │  → runs/YYYY-MM-DD/  │
   │ validasi vs fact   │      └──────────┬───────────┘
   │ table              │                 │
   └─────────┬──────────┘                 │
             └──────────────┬─────────────┘
                            ▼
                ┌────────────────────────┐
                │  WEB (Next.js)         │  baca JSON statis
                │  Ticker · Papan Waspada│  ZERO panggilan API
                │  · Metodologi          │  saat runtime  [K2]
                └────────────────────────┘

   Orkestrasi: GitHub Actions cron 17:30 WIB hari bursa
   → commit artefak ke runs/ = bukti unattended run ber-timestamp  [T5]
```

### Keputusan arsitektur kunci

**AD-1 — Web app tidak pernah memanggil Sectors API saat runtime.**
Pipeline memprakomputasi semuanya ke JSON statis. Konsekuensi: demo tidak bisa gagal karena latency/rate limit, biaya kredit nol per pengunjung, dan juri bisa menjalankan repo tanpa API key. `[K1][K2][T9]`

**AD-2 — Snapshot warehouse di-commit ke repo.**
`data/warehouse/*.parquet` masuk git (ukuran ditekan, ±20–40 MB). Juri clone → `make demo` → sistem penuh jalan tanpa kredensial apa pun. Ini menjawab langsung ketakutan juri "video bagus, kode kosong". `[K4][T7]`

**AD-3 — Cache disk permanen, bukan TTL.**
Respons API disimpan sebagai file berkunci hash `(endpoint, params)` di `data/cache/`. Data historis IDX tidak berubah, jadi panggilan ulang selama pengembangan **gratis selamanya**. Ini yang membuat 1.000 kredit cukup. `[K1]`

**AD-4 — LLM di luar jalur kritis.**
Skor, band, dan Papan Waspada dihitung tanpa LLM. LLM hanya menyusun narasi Bahasa Indonesia **dari fact table terstruktur**, dan outputnya divalidasi: setiap angka dalam narasi harus cocok dengan entri di fact table, kalau tidak → fallback ke template deterministik. Halusinasi angka secara struktural mustahil lolos. `[T12]`
> Catatan track: LLM opsional di Track 3. Kalau layer ini bermasalah, produk tetap utuh. `[K2]`

**AD-5 — Ledger kredit ditegakkan di kode, bukan di kepala.**
`CreditAwareClient` menolak panggilan yang akan melampaui pagu fase, mencatat tiap panggilan ke `data/credit_ledger.jsonl`, dan ledger ini **di-commit ke repo sebagai bukti disiplin rekayasa** yang bisa dilihat juri. `[K1][T7]`

**AD-6 — Track 3, bukan Track 1 atau 2.**
Inti produk adalah insight turunan (skor, ranking, deteksi anomali) — persis definisi Track 3. Track 1 akan jadi track paling padat dan menuntut LLM sebagai inti, padahal kekuatan kita ada di skoring deterministik. Track 2 adalah ide paling mudah ditebak ("daily brief bot"). Kita tetap **menampilkan bukti unattended run di video** — mengambil keuntungan T2 tanpa masuk kandangnya. `RESEARCH.md` §1

---

## 5. Kalibrasi & Validasi (ini yang bikin menang) `[T6]`

Tanpa ini, PANTAU cuma enam angka yang kelihatan pintar.

**Sumber label:** `fetch-suspensions` — riwayat suspensi IDX beserta alasan resmi. Suspensi karena pergerakan harga tidak wajar adalah proksi peristiwa yang paling mendekati "kejadian yang seharusnya kita peringatkan".

**Protokol:**
1. Tarik seluruh suspensi 24 bulan terakhir. Saring yang alasannya terkait pergerakan harga/aktivitas tidak wajar → **himpunan positif**.
2. Sampel kontrol: saham dengan kapitalisasi & subsektor serupa yang tidak pernah disuspend pada periode sama → **himpunan negatif**.
3. Hitung 6 sub-skor pada **T-1, T-3, T-5, T-10 hari bursa** sebelum tanggal peristiwa (strictly point-in-time, tanpa lookahead).
4. Cari bobot `wᵢ` yang memaksimalkan pemisahan (logistic regression sederhana, atau grid search — dipilih yang bisa dijelaskan dalam 15 detik di video).
5. **Split waktu:** kalibrasi pada 18 bulan pertama, uji pada 6 bulan terakhir yang belum pernah dilihat.

**Metrik yang dilaporkan (angka tunggal untuk video):**
- Precision@20 pada Papan Waspada out-of-sample
- Recall peristiwa suspensi pada ambang skor ≥60
- **Median lead time** — berapa hari bursa sebelumnya PANTAU sudah menyalakan lampu

**Kejujuran wajib:** himpunan positif kecil, dan suspensi bukan sinonim manipulasi. Batasan ini ditulis terbuka di halaman Metodologi dan disebut di video. Juri praktisi pasar akan langsung tahu kalau kita melebih-lebihkan; mengakuinya duluan justru menambah kredibilitas. `[T7]`

Semua ini hidup di `notebooks/calibration.ipynb` + `reports/validation.md`, di-commit ke repo.

---

## 6. Anggaran Kredit (pagu keras: 1.000)

| Fase | Alokasi | Rincian |
| --- | --- | --- |
| Eksplorasi & pengembangan | 150 | dilindungi cache permanen `[AD-3]` |
| Backfill historis + kalibrasi | 450 | `fetch-close` 120 hari bursa (±120), suspensi & filings market-wide (±30), Tier-2 untuk himpunan positif+kontrol (±300) |
| Operasi pipeline harian | 300 | ±12 kredit × 25 hari |
| **Cadangan** | **100** | retry, rekaman ulang video, kegagalan tak terduga |

Aturan yang ditegakkan `CreditAwareClient`:
- Panggilan yang akan menembus pagu fase → **ditolak**, bukan diperingatkan.
- Cache hit tidak dihitung.
- Alarm di 70% dan 90% pemakaian total.
- Ledger di-commit; `make credits` mencetak posisi terkini.

---

## 7. Tumpukan Teknologi

Prinsip: **membosankan, bisa diaudit, jalan di mesin bersih.** `[T7][T9]`

| Lapis | Pilihan | Alasan |
| --- | --- | --- |
| Ingestion & scoring | Python 3.12, `httpx`, `pandas`, `pydantic` | ekosistem data paling ringkas; pydantic memaksa skema respons tervalidasi |
| Snapshot store | **DuckDB + Parquet** | file tunggal, nol server, bisa di-commit, query SQL analitik cepat |
| Narrative layer | Claude via Anthropic SDK, output JSON terstruktur | dipagari validator fact-table `[AD-4]` |
| Web | **Next.js 15 (App Router) + Tailwind + Recharts**, output statis | satu orang bisa pegang penuh; deploy Vercel sekali klik |
| Orkestrasi | **GitHub Actions cron** | konfigurasi schedule terlihat di repo, log ber-timestamp otomatis jadi bukti `[T5]` |
| Kualitas | `pytest`, `ruff`, pre-commit | tes pada scoring engine = bukti "bukan dipalsukan" |
| Deploy | Vercel (web) | tidak ada backend runtime yang bisa mati saat penjurian |

**Yang sengaja TIDAK dipakai:** Postgres, Redis, Docker Compose multi-service, Celery, message queue, auth. Semua menambah permukaan gagal tanpa menambah satu poin pun di rubrik.

---

## 8. Struktur Repositori

```
pantau/
├── README.md                  ← etalase untuk juri: diagram, tabel endpoint, quickstart
├── ARCHITECTURE.md
├── RESEARCH.md
├── TASK.md
├── SUBMISSION.md              ← checklist freeze
├── Makefile                   ← make demo | make pipeline | make credits | make test
│
├── core/
│   ├── sectors/
│   │   ├── client.py          ← CreditAwareClient (ledger, cache, retry)
│   │   ├── endpoints.py       ← wrapper per endpoint + biaya kredit tercatat
│   │   └── schemas.py         ← model pydantic tiap respons
│   ├── ingest/
│   │   ├── tier1_market.py    ← sapuan market-wide harian
│   │   ├── tier2_deep.py      ← pendalaman per-ticker untuk kandidat
│   │   └── backfill.py        ← tarikan historis untuk kalibrasi
│   ├── scoring/
│   │   ├── bci.py  vas.py  pfd.py  ffs.py  frd.py  sss.py
│   │   ├── composite.py       ← pembobotan + band
│   │   └── facts.py           ← fact table: nilai + endpoint + as_of + url sumber
│   ├── narrative/
│   │   ├── generate.py        ← prompt LLM di atas fact table
│   │   └── validate.py        ← tolak narasi yang angkanya tidak ada di fact table
│   └── export/
│       └── to_json.py         ← tulis public/data/ + runs/
│
├── data/
│   ├── cache/                 ← cache disk permanen (gitignored)
│   ├── warehouse/*.parquet    ← DI-COMMIT: juri bisa jalan tanpa API key
│   └── credit_ledger.jsonl    ← DI-COMMIT: bukti disiplin kredit
│
├── runs/YYYY-MM-DD/           ← DI-COMMIT otomatis oleh cron: bukti unattended run
│   ├── watchlist.json
│   └── run.log
│
├── notebooks/calibration.ipynb
├── reports/validation.md      ← angka yang dikutip di video
├── tests/                     ← unit test tiap komponen skor + kasus batas
│
├── web/                       ← Next.js
│   ├── app/(ticker|papan|metodologi)/
│   └── public/data/*.json
│
├── .github/workflows/daily.yml  ← cron 10:30 UTC = 17:30 WIB, Sen–Jum
└── video/
    ├── script-judging.md      ← DITULIS SEBELUM COMMIT PERTAMA  [T2]
    └── script-teaser.md
```

---

## 9. Kontrak Data Internal

Satu bentuk data mengalir dari scoring ke narrative ke web. Ini yang membuat sitasi terjamin.

```jsonc
// FactTable — satu entri per angka yang boleh muncul di narasi
{
  "id": "bci.top3_share",
  "label": "Pangsa net buy 3 broker teratas",
  "value": 0.78,
  "display": "78%",
  "source_endpoint": "fetch-broker-summary-top",
  "source_params": { "symbol": "XXXX", "start": "2026-09-01", "end": "2026-09-05" },
  "as_of": "2026-09-05T17:30:00+07:00"
}
```

```jsonc
// TickerScore — payload halaman ticker
{
  "symbol": "XXXX",
  "as_of": "2026-09-05",
  "pantau_score": 74,
  "band": "waspada",
  "components": [
    { "code": "BCI", "score": 88, "weight": 0.24, "facts": ["bci.top3_share", "bci.hhi"] }
    // ...
  ],
  "narrative_id": "…",
  "disclaimer": "PANTAU adalah alat informasi dan analisis, bukan saran investasi."
}
```

Validator `narrative/validate.py`: setiap token angka dalam narasi harus punya padanan di `facts`. Gagal → pakai template deterministik. `[AD-4]`

---

## 10. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Kredit habis sebelum kalibrasi selesai | Fatal | Pagu per fase ditegakkan di kode; cache permanen; backfill dijalankan lebih dulu `[AD-3][AD-5]` |
| Himpunan suspensi terlalu kecil → validasi lemah | Sedang | Tambah label sekunder (lonjakan volume ekstrem + pembalikan tajam); nyatakan batasan secara terbuka `[T7]` |
| Endpoint broker summary tidak mengembalikan kedalaman yang diasumsikan | Tinggi | **Spike hari-1**: verifikasi bentuk respons semua endpoint kritis sebelum apa pun dibangun di atasnya |
| Layer LLM tidak stabil | Rendah | LLM opsional di T3; fallback template deterministik `[AD-4]` |
| Dianggap memberi saran finansial | Fatal (diskualifikasi) | Larangan kosakata di CI: grep kata "beli/jual/target harga/rekomendasi" pada seluruh string output |
| Kelewat deadline / kelengkapan submission | Fatal | Feature freeze 26 Sep, submit 29 Sep `[T15]`, `SUBMISSION.md` |
| Overscope | Tinggi | Skrip video ditulis lebih dulu = spec; apa pun di luar skrip ditolak `[T2]` |

---

## 11. Definition of Done

Produk selesai ketika, di mesin bersih tanpa API key:

```bash
git clone <repo> && cd pantau && make demo
```

membuka aplikasi berisi data snapshot nyata, halaman ticker menampilkan skor + narasi tersitasi, Papan Waspada menampilkan arsip berjalan bertanggal, halaman Metodologi menampilkan bobot dan angka validasi — dan `runs/` berisi minimal **10 hari bursa berturut-turut** artefak yang di-commit oleh cron tanpa disentuh manusia. `[T5][T7]`
