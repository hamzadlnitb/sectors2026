# ARCHITECTURE.md — PANTAU

> **PANTAU** — agen investigasi risiko manipulasi & likuiditas saham IDX.
> Sectors Hackathon 2026 · **Track 1 — AI Agents & Assistants**

Semua keputusan di dokumen ini punya jejak ke `RESEARCH.md`. Nomor taktik `[Tn]` merujuk ke bagian 3 dokumen tersebut.

---

## 1. Ringkasan Produk

### Problem statement (1 kalimat, untuk form submission)
> Untuk investor ritel IDX yang menerima rekomendasi saham dari grup Telegram dan TikTok, PANTAU adalah agen yang menyelidiki satu saham seperti analis sungguhan — memutuskan sendiri bukti apa yang layak dikejar, lalu menjawab satu pertanyaan yang tidak bisa dijawab aplikasi sekuritas mana pun: *"saham ini lagi ramai — ini nyata atau digoreng?"*

### Persona (satu, tidak lebih) `[T1]`
**Rina, 26 tahun, Bekasi.** Bagian dari 54,12% investor IDX di bawah 30 tahun. Modal Rp 20 juta di aplikasi sekuritas. Dapat ticker dari grup Telegram. Tidak tahu cara baca broker summary, tidak tahu apa itu free float, tidak tahu saham itu sedang di Papan Pemantauan Khusus. Yang dia butuhkan bukan rekomendasi beli — dia butuh **tahu kalau dia sedang jadi exit liquidity.**

### Bentuk produk
1. **Investigasi** — masukkan kode saham → agen menyusun rencana penyelidikan, mengeksekusinya langkah demi langkah sambil beradaptasi terhadap temuan, lalu mengeluarkan **Skor PANTAU 0–100** + putusan bernarasi Bahasa Indonesia. **Seluruh jejak penalaran ditampilkan**: rencana awal, tiap langkah, apa yang ditemukan, dan keputusan agen untuk lanjut / mendalami / berhenti.
2. **Buku Bukti** — setiap angka dalam putusan bisa diklik balik ke endpoint Sectors + parameter + `as-of`. Agen tidak boleh menyatakan apa pun yang tidak ada di buku bukti. `[T12]`
3. **Papan Waspada** — tiap hari bursa agen menyelidiki sendiri saham-saham teratas hasil penyaringan pasar, tanpa disuruh. Arsip investigasi bertanggal, tersimpan di repo. `[T5]`
4. **Halaman Metodologi** — rumus tiap komponen, bobot hasil kalibrasi, hasil backtest, dan **efisiensi perutean agen**. `[T6][T7]`

### Kenapa produk ini butuh agen (bukan agen yang mencari alasan)
Ini pertanyaan yang akan ditanyakan juri, dan jawabannya harus datang dari kendala nyata, bukan dari selera arsitektur.

**Data Sectors mahal dan jatah kita 1.000 kredit.** Menyelidiki satu saham secara menyeluruh berarti menembak keenam jalur bukti — mahal, dan sebagian besar sia-sia karena mayoritas saham normal. Yang mahal bukan menghitung skor, tapi **memutuskan bukti mana yang layak dibeli untuk saham ini, hari ini.**

Itu keputusan yang bergantung konteks: saham lapis ketiga yang volumenya meledak butuh probe broker; emiten besar yang harganya menjauh dari fundamental butuh probe divergensi; saham yang minggu lalu sudah diselidiki cuma butuh delta. Aturan if-else akan pecah menghadapi ragam kasus ini. **Agen ada di sini untuk menghemat uang, bukan untuk terlihat modern.**

Konsekuensinya, klaim utama kita bisa diukur: *penyelidikan menyeluruh butuh N kredit; perencana kami rata-rata Y kredit dan menghasilkan putusan yang sama Z% dari waktu.* `[T6]`

### Kenapa ini, bukan ide lain
| Alasan | Bukti |
| --- | --- |
| Framing **perlindungan investor**, bukan saran finansial → aman terhadap larangan rules | `RESEARCH.md` §1 aturan keras, `[T13]` |
| Bersandar pada data yang **cuma Sectors punya** (broker summary, foreign flow, free float, suspensi, filings) | `[T3]` |
| **Tidak ada** di pustaka recipe resmi Sectors → tidak menyerahkan tutorial juri ke jurinya sendiri | `[T4]` |
| Ada **label alami** (`fetch-suspensions`) → bisa dikalibrasi & di-backtest → menghasilkan angka terukur | `[T6]` |
| Relevan dengan debat **Papan Pemantauan Khusus / FCA** yang sedang berjalan di OJK–IDX–Komisi XI | `[T13]` |
| Bukan chatbot "ngobrol sama saham" — agen investigasi dengan deliverable terstruktur | `RESEARCH.md` §3 daftar jangan-dibangun #1 |

### Uji "cabut Sectors" (gerbang eligibility)
Cabut Sectors → tidak ada broker summary, foreign flow, free float, riwayat suspensi. Keenam alat penyelidik agen mati; tidak ada yang bisa direncanakan maupun diputuskan. **Produk tinggal cangkang kosong.** Lolos.

### Uji anti-diskualifikasi Track 1
> *"Kalau produknya hilang begitu prompt kalian dicabut dari klien orang lain, tidak lolos."*

Cabut prompt PANTAU dari klien mana pun dan yang tersisa di kode kami tetap: perencana, loop penyelidik dengan penganggaran dan penghentian dini, buku bukti, mesin skoring deterministik enam komponen, memori investigasi per-ticker, validator sitasi, dan antarmuka jejak penalaran. **LLM adalah satu komponen di dalam sistem kami, bukan sistemnya.** Lolos. `RESEARCH.md` §1 tabel track

---

## 2. Kendala yang Menyetir Arsitektur

| # | Kendala | Implikasi arsitektur |
| --- | --- | --- |
| K1 | **1.000 kredit API total**, biaya 1–3 kredit/panggilan | Mustahil query live per request. Ingestion batch + snapshot lokal + **ledger kredit ditegakkan di kode**. Dan: **inilah alasan keberadaan agen** |
| K2 | Penjurian **asinkron**, tanpa pitch live | Jalur demo harus mustahil gagal. Investigasi direkam sebagai transkrip yang bisa diputar ulang; **nol pemanggilan LLM saat demo** `[T9]` |
| K3 | **Freeze total** saat submit, tanpa bug fix | Feature freeze internal H-4. Buffer submit 24 jam `[T15]` |
| K4 | Repo **diverifikasi juri** | README, diagram, tabel endpoint, one-command run, tes, commit history rapi `[T7]` |
| K5 | Dilarang saran finansial | Tidak ada kata "beli/jual/target harga" di seluruh output, termasuk output LLM. Disclaimer permanen |
| K6 | Dilarang eksekusi order | Nol integrasi broker. Nol kode order |
| K7 | Data Sectors EOD (bukan realtime) | Dibingkai sebagai investigasi harian pasca-tutup, bukan alat intraday |
| **K8** | **LLM nondeterministik; Track 1 mewajibkannya jadi inti** | Agen boleh memutuskan **apa yang diselidiki**; agen **tidak pernah** memutuskan berapa skornya. Angka selalu dari kode deterministik `[AD-4]` |
| **K9** | **Biaya LLM terpisah dari kredit Sectors** | Anggaran token sendiri; transkrip di-cache; eval agen dijalankan dengan model kecil dulu |

---

## 3. Desain Agen

Tiga tahap orkestrasi buatan sendiri. Ini inti Track 1 dan bagian yang paling harus terlihat di repo.

```
       ticker + sinyal pasar Tier-1 (gratis, dari warehouse)
                          │
              ┌───────────▼───────────┐
              │  1. PERENCANA         │  LLM
              │  Menyusun rencana     │  → hipotesis + jalur bukti terurut
              │  penyelidikan         │  → pagu kredit yang diminta
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │  2. PENYELIDIK (loop) │  LLM memutuskan rute,
              │                       │  alat deterministik mengeksekusi
              │  eksekusi langkah     │
              │      ↓                │  Setiap langkah:
              │  evaluasi temuan      │   • panggil satu probe
              │      ↓                │   • catat ke buku bukti
              │  lanjut / dalami /    │   • hipotesis: terkonfirmasi,
              │  berhenti             │     terbantah, atau tak jelas
              └───────────┬───────────┘
                          │  Pagar keras: maks 8 langkah,
                          │  maks 25 kredit, timeout
              ┌───────────▼───────────┐
              │  3. PENILAI           │  Skor: KODE DETERMINISTIK
              │  Buku bukti → skor    │  Narasi: LLM, divalidasi
              │  → putusan bernarasi  │  ketat vs buku bukti
              └───────────┬───────────┘
                          ▼
              Transkrip investigasi (JSON, bisa diputar ulang)
                          │
              ┌───────────▼───────────┐
              │  MEMORI per-ticker    │  Investigasi berikutnya dimulai
              │  (DuckDB)             │  dari "apa yang berubah"
              └───────────────────────┘
```

### Alat yang dimiliki agen
Alat agen adalah **milik kami**, bukan endpoint Sectors mentah. Tiap probe membungkus beberapa panggilan Sectors, menghitung sub-skor, dan mengembalikan bukti terstruktur berikut biayanya.

| Alat | Biaya | Mengembalikan |
| --- | --- | --- |
| `screen_market()` | **0** | Kandidat + sinyal Tier-1 dari warehouse |
| `recall_history(symbol)` | **0** | Investigasi sebelumnya + delta sejak saat itu |
| `probe_broker_concentration(symbol, window)` | 2–6 | **BCI** — HHI net buy, pangsa 3 broker teratas |
| `probe_volume_anomaly(symbol)` | 1–3 | **VAS** — z-score volume vs baseline 90 hari |
| `probe_price_fundamental(symbol)` | 2–5 | **PFD** — return vs perubahan laba/valuasi |
| `probe_free_float(symbol)` | 1–2 | **FFS** — kelangkaan saham beredar |
| `probe_foreign_flow(symbol)` | 2–4 | **FRD** — arus asing keluar saat harga naik |
| `probe_structural(symbol)` | 2–5 | **SSS** — suspensi, insider filings, corporate actions |
| `conclude(reason)` | 0 | Mengakhiri investigasi |

Enam probe = enam komponen skor di §4. Semuanya fungsi murni, tertes unit, dan bisa dipanggil tanpa agen sama sekali.

### Yang membuat loop ini benar-benar agentik
Bukan karena ada LLM di dalamnya, tapi karena empat perilaku ini **terlihat di transkrip**:

- **Perutean adaptif** — agen membuka jalur bukti yang **tidak ada di rencana awal** ketika temuan mengejutkan. Contoh: VAS normal tapi FRD ekstrem → agen membuka `probe_structural` untuk mencari filings insider, padahal rencana awal tidak memuatnya.
- **Penghentian dini** — agen berhenti begitu bukti sudah cukup, menghemat kredit. Investigasi yang jelas-jelas normal harus berhenti setelah 2 langkah.
- **Eskalasi** — agen meminta tambahan pagu kredit dengan alasan tertulis; permintaan bisa ditolak oleh penganggaran, dan agen harus menyimpulkan dengan bukti yang ada.
- **Memori** — investigasi ulang atas ticker yang sama menghasilkan rencana **berbeda**, karena diarahkan ke apa yang berubah.

Keempatnya harus tampil di video. Tanpa ini, agen terlihat seperti if-else berbaju LLM. `[T11]`

### Kontrak jejak penalaran
Perencana dan penyelidik hanya boleh mengeluarkan JSON terstruktur, tidak pernah prosa bebas:

```jsonc
// keluaran Perencana
{ "hypotheses": [ { "id": "h1", "claim": "Volume tidak wajar tanpa dukungan fundamental",
                    "probes": ["volume_anomaly", "price_fundamental"], "priority": 1 } ],
  "credit_budget_requested": 12,
  "rationale": "Sinyal Tier-1: volume 6,2σ, kapitalisasi kecil, tidak ada investigasi sebelumnya" }

// keputusan Penyelidik tiap langkah
{ "step": 3, "hypothesis": "h1", "finding": "confirmed",
  "next_action": "escalate", "new_probe": "structural",
  "reason": "Volume ekstrem + free float 4% menuntut pemeriksaan corporate action",
  "credits_spent": 7, "credits_remaining": 5 }
```

Prosa bebas hanya muncul di satu tempat: narasi Penilai — dan di sana ia lewat validator sitasi.

---

## 4. Enam Komponen Skor PANTAU

Skor komposit dihitung dari enam sub-skor independen, masing-masing dinormalisasi ke 0–100. Semuanya **deterministik dan murni fungsional** — **tidak ada LLM di jalur perhitungan.** `[K8]`

| Kode | Komponen | Pertanyaan yang dijawab | Sumber data Sectors |
| --- | --- | --- | --- |
| **BCI** | Broker Concentration Index | Berapa persen net buy dikuasai 3 broker teratas? (HHI) | `fetch-broker-summary-top`, `fetch-broker-summary` |
| **VAS** | Volume Anomaly Score | Volume hari ini berapa sigma di atas baseline 90 hari? | `fetch-daily-transaction`, `fetch-most-traded-stocks` |
| **PFD** | Price–Fundamental Divergence | Harga naik 200% sementara laba flat/rugi? | `fetch-company-report`, `fetch-quarterly-financials`, `fetch-close` |
| **FFS** | Free Float Scarcity | Berapa kecil saham yang benar-benar beredar? | `fetch-free-float`, `fetch-company-report` |
| **FRD** | Foreign–Retail Divergence | Asing keluar sementara harga naik = distribusi ke ritel? | `fetch-foreign-flow`, `fetch-shareholders-composition` |
| **SSS** | Structural Signal Score | Pernah disuspend? Insider jual saat harga naik? Rights issue beruntun? | `fetch-suspensions`, `fetch-filings`, `fetch-corporate-actions` |

```
PANTAU = Σ (wᵢ · sub_skorᵢ) / Σ wᵢ   — hanya atas komponen yang benar-benar diselidiki
```

Karena agen boleh berhenti lebih awal, skor dihitung atas komponen yang tersedia dan **selalu dilaporkan bersama tingkat keyakinannya** (berapa bobot yang tercakup). Investigasi 2 langkah menghasilkan skor berkeyakinan rendah, dan UI menyatakannya terang-terangan.

Bobot `wᵢ` **tidak ditebak** — dikalibrasi pada peristiwa historis berlabel (§6). `[T6]`

### Band interpretasi
| Skor | Band | Bahasa di UI |
| --- | --- | --- |
| 0–29 | Normal | "Tidak ada pola tidak biasa terdeteksi" |
| 30–59 | Perlu diperhatikan | "Ada beberapa pola yang layak dicermati" |
| 60–79 | Waspada | "Beberapa indikator menunjukkan pola tidak biasa" |
| 80–100 | Sangat waspada | "Banyak indikator menunjukkan pola tidak biasa secara bersamaan" |

Tidak ada band yang berbunyi "jual" atau "hindari". `[K5]`

---

## 5. Arsitektur Sistem

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
        │  Tier 1 — market-wide, ±6 kredit/hari  │
        │    fetch-close (1 call = semua ticker) │
        │    most-traded · top-changes           │
        │    suspensions · filings               │
        │  Tier 2 — hanya lewat probe agen       │
        └───────────────────┬────────────────────┘
                            ▼
                ┌────────────────────────┐
                │  SNAPSHOT STORE        │  DuckDB + Parquet
                │  (data/warehouse/)     │  di-commit ke repo
                └───────────┬────────────┘
                            ▼
        ┌───────────────────────────────────────┐
        │  LAPISAN PROBE (core/probes/)         │  deterministik,
        │  6 probe → sub-skor + entri bukti     │  tertes unit
        └───────────────────┬───────────────────┘
                            ▼
        ┌───────────────────────────────────────┐
        │  AGEN (core/agent/)                   │
        │  perencana → penyelidik → penilai     │  ← §3
        │  + memori + penganggaran + pagar      │
        └───────────────────┬───────────────────┘
                            ▼
        ┌───────────────────────────────────────┐
        │  TRANSKRIP INVESTIGASI                │
        │  runs/investigations/<sym>-<tgl>.json │  bisa diputar ulang
        └───────────────────┬───────────────────┘
                            ▼
                ┌────────────────────────┐
                │  WEB (Next.js)         │  memutar ulang transkrip
                │  Investigasi · Papan   │  ZERO panggilan API & LLM
                │  Waspada · Metodologi  │  saat runtime  [K2]
                └────────────────────────┘

   Orkestrasi: GitHub Actions cron 17:30 WIB hari bursa
   → agen menyelidiki sendiri top-N, commit transkrip ke runs/
   = bukti operasi otonom ber-timestamp  [T5]
```

### Keputusan arsitektur kunci

**AD-1 — Web app tidak pernah memanggil Sectors API maupun LLM saat runtime.**
Semua investigasi diprakomputasi jadi transkrip JSON; web memutarnya ulang langkah demi langkah. Demo tidak bisa gagal karena latency, rate limit, atau LLM yang ngambek. Juri bisa memutar investigasi yang sama berkali-kali dan mendapat hasil identik. `[K1][K2][T9]`

**AD-2 — Snapshot warehouse + transkrip di-commit ke repo.**
Juri clone → `make demo` → sistem penuh jalan tanpa kredensial apa pun. Dengan API key mereka sendiri, `make investigate BBCA` menjalankan agen sungguhan. Dua tingkat pembuktian. `[K4][T7]`

**AD-3 — Cache disk permanen, bukan TTL.**
Respons API disimpan berkunci hash `(endpoint, params)`. Data historis IDX tidak berubah → panggilan ulang selama pengembangan **gratis selamanya**. Ini yang membuat 1.000 kredit cukup, dan membuat eval agen bisa dijalankan berulang kali tanpa biaya. `[K1]`

**AD-4 — Agen memutuskan APA yang diselidiki; kode memutuskan BERAPA skornya.**
Pembagian ini tidak boleh kabur. LLM: menyusun rencana, memilih probe, memutuskan lanjut/berhenti, menulis narasi. Kode: menghitung tiap sub-skor, membobot komposit, menetapkan band. Narasi divalidasi — setiap token angka wajib punya padanan di buku bukti, gagal → fallback template deterministik. Halusinasi angka secara struktural mustahil lolos. `[K8][T12]`

**AD-5 — Ledger kredit ditegakkan di kode, bukan di kepala.**
`CreditAwareClient` menolak panggilan yang melampaui pagu fase, mencatat tiap panggilan ke `data/credit_ledger.jsonl`. Agen punya pagu keduanya: per-investigasi (25 kredit) dan per-hari. Ledger di-commit sebagai bukti disiplin rekayasa. `[K1][T7]`

**AD-6 — Agen dipagari keras, bukan dipercaya.**
Maks 8 langkah, maks 25 kredit per investigasi, timeout per langkah, keluaran wajib lolos skema JSON, dan tiap probe hanya boleh dipanggil sekali per investigasi. Melewati pagar mana pun → investigasi ditutup dengan bukti yang sudah terkumpul, bukan gagal. Agen yang tidak bisa mengunci dirinya sendiri tidak layak jalan tanpa pengawasan. `[K8]`

**AD-7 — Satu gateway terukur, dua transport. MCP bukan cuma alat bantu pengembangan.**

Kriteria teknis 30% berbunyi *"how innovative is the use of Sectors API **or MCP**"*. MCP disebut setara, dan panitia sendiri yang membangun serta mendokumentasikan server MCP-nya. Menaruh MCP hanya di jalur pengembangan berarti meninggalkan poin di meja.

Semua akses ke Sectors — REST maupun MCP — lewat `CreditAwareClient` yang sama. Karena klien MCP-nya kita tulis sendiri (bukan klien jadi milik orang lain), tiap tool call bisa dicegat, dihitung biayanya, dan dicatat ke ledger persis seperti panggilan REST. Alasan "hanya REST yang bisa diukur" tidak berlaku begitu kita memiliki kliennya.

Pembagian transport ditentukan **per-endpoint di sebuah tabel**, bukan diputuskan LLM per-panggilan — LLM memilih *alat*, bukan *transport*:

| Jalur | Transport | Alasan |
| --- | --- | --- |
| Sapuan Tier-1 harian, backfill massal | **REST** | `fetch-close` dan sejenisnya butuh panggilan presisi, batched, dan murah |
| Ekor panjang tool spesialis yang dipakai probe | **MCP** | 65+ tool siap pakai; tidak perlu menulis 65 wrapper REST tangan |
| Penyaringan bahasa alami (`fetch-companies-by-subsector` argumen `q`) | **MCP** | kemampuan yang tidak muncul kalau kita bungkus REST sendiri |

**Yang membuat ini "innovative use of MCP", bukan sekadar "memakai MCP":** perencana agen melihat katalog tool MCP **beserta harga kreditnya**, lalu memilih di bawah pagu anggaran. Pemilihan tool MCP yang sadar biaya — itu yang tidak ada di recipe resmi mana pun, dan itu yang jadi Angka 2 di §6. `[K1][T3]`

> **Yang tetap dijaga:** ini tidak melunakkan syarat Track 1. Yang didiskualifikasi adalah *menyambungkan klien AI jadi ke MCP dengan prompt*. Kita menulis klien MCP sendiri, di dalam orkestrasi sendiri, dengan penganggaran dan pagar sendiri. `RESEARCH.md` §1 tabel track

**AD-8 — Kualitas rekayasa adalah bukti, bukan kerapian.**

Separuh kedua kriteria teknis berbunyi *"real, functional, **well engineered**, and not faked for the demo"*. Ini dinilai dari repo, jadi hal-hal berikut bukan kebersihan opsional — ini alat bukti, dan tiap satunya menjawab satu kecurigaan juri:

| Artefak | Kecurigaan yang dijawab |
| --- | --- |
| `make demo` jalan tanpa API key | "apakah ini benar-benar bisa dijalankan?" |
| Tes pagar agen (ngelantur, pagu habis, skema rusak) | "apakah agennya beneran atau cuma jalan di happy path?" |
| Tes validator sitasi dengan buku bukti dipalsukan | "apakah angkanya dikarang LLM?" |
| `data/credit_ledger.jsonl` ter-commit | "apakah pemakaian API-nya nyata dan seirit yang diklaim?" |
| `evals/` dengan ablasi | "apakah agennya menambah nilai, atau cuma hiasan?" |
| Riwayat commit bertahap | "apakah ini dibangun, atau ditempel semalam?" |
| Skema pydantic di tiap batas | "apakah ini rapuh?" |

Tiap baris di tabel ini masuk README sebagai tautan langsung ke berkasnya. Juri tidak perlu mencari. `[T7]`

---

## 6. Kalibrasi & Validasi (ini yang bikin menang) `[T6]`

Kita membawa **dua angka**, dan angka kedua adalah yang paling sulit ditandingi tim lain.

### Angka 1 — apakah skornya berarti?
**Sumber label:** `fetch-suspensions` — riwayat suspensi IDX beserta alasan resmi. Suspensi karena pergerakan harga tidak wajar adalah proksi terdekat untuk "kejadian yang seharusnya kita peringatkan".

**Protokol:**
1. Tarik seluruh suspensi 24 bulan terakhir; saring alasan terkait pergerakan/aktivitas tidak wajar → **himpunan positif**.
2. Sampel kontrol tersamakan berdasarkan kapitalisasi & subsektor → **himpunan negatif**.
3. Hitung 6 sub-skor pada **T-1, T-3, T-5, T-10 hari bursa** sebelum peristiwa — **strictly point-in-time, nol lookahead**.
4. Cari bobot `wᵢ` (logistic regression atau grid search; pilih yang bisa dijelaskan dalam 15 detik).
5. **Split waktu:** kalibrasi 18 bulan pertama, uji 6 bulan terakhir yang belum pernah dilihat.

Dilaporkan: Precision@20, recall pada ambang ≥60, **median lead time**.

### Angka 2 — apakah agennya berarti?
Ini yang membuktikan agen bukan hiasan, dan langsung menjawab kriteria teknis 30%.

**Baseline:** investigasi menyeluruh — keenam probe dijalankan pada tiap ticker uji. Catat total kredit dan putusan.
**Perlakuan:** agen menginvestigasi ticker yang sama dengan perencanaan adaptif.

Dilaporkan:
- **Kredit per investigasi** — agen vs menyeluruh (target: penghematan ≥50%)
- **Kesepakatan band** — persentase putusan agen yang sama bandnya dengan baseline menyeluruh (target: ≥90%)
- **Presisi eskalasi** — ketika agen membuka probe di luar rencana, seberapa sering probe itu memang menghasilkan bukti yang mengubah band
- **Ablasi:** agen vs pengurutan tetap (semua probe, urutan tetap) vs pemilihan acak dengan pagu sama. Kalau agen tidak mengalahkan urutan tetap, kita punya masalah dan harus tahu **sebelum** merekam video

**Kejujuran wajib:** himpunan positif kecil, dan suspensi bukan sinonim manipulasi. Batasan ini ditulis terbuka di halaman Metodologi dan disebut di video. Juri praktisi pasar akan tahu kalau kita melebih-lebihkan; mengakuinya duluan justru menambah kredibilitas. `[T7]`

Hidup di `notebooks/calibration.ipynb`, `evals/agent_eval.py`, `reports/validation.md`.

---

## 7. Anggaran Kredit (pagu keras: 1.000)

| Fase | Alokasi | Rincian |
| --- | --- | --- |
| Eksplorasi & pengembangan probe | 120 | dilindungi cache permanen `[AD-3]` |
| Backfill historis + kalibrasi bobot | 400 | `fetch-close` 120 hari bursa (±120), suspensi & filings market-wide (±30), Tier-2 untuk himpunan positif + kontrol (±250) |
| Eval agen (baseline + perlakuan + ablasi) | 130 | sebagian besar kena cache setelah putaran pertama |
| Operasi harian (agen otonom) | 250 | ±10 kredit/hari × 25 hari |
| **Cadangan** | **100** | retry, rekaman ulang video, kegagalan tak terduga |

Aturan yang ditegakkan `CreditAwareClient`: panggilan yang menembus pagu fase **ditolak**, bukan diperingatkan. Cache hit tidak dihitung. Alarm di 70% dan 90%. `make credits` mencetak posisi terkini.

**Anggaran LLM terpisah** `[K9]`: transkrip di-cache berkunci `(ticker, tanggal, versi_prompt)`; eval agen dijalankan pakai model kecil sampai perilakunya stabil, baru dinaikkan.

---

## 8. Tumpukan Teknologi

Prinsip: **membosankan, bisa diaudit, jalan di mesin bersih.** `[T7][T9]`

| Lapis | Pilihan | Alasan |
| --- | --- | --- |
| Ingestion, probe, agen | Python 3.12, `httpx`, `pandas`, `pydantic` | pydantic memaksa keluaran agen tervalidasi skema — pagar `[AD-6]` |
| Akses Sectors | **klien MCP tulis sendiri** (`mcp` SDK, Streamable HTTP) + REST `httpx`, keduanya di balik `CreditAwareClient` | tiap tool call MCP tercegat dan termeter seperti REST `[AD-7]` |
| Snapshot store & memori | **DuckDB + Parquet** | file tunggal, nol server, bisa di-commit |
| LLM | Claude via Anthropic SDK, tool use + keluaran JSON terstruktur | orkestrasi ditulis sendiri, bukan framework agen pihak ketiga — supaya logika agen terlihat di repo kita `[T11]` |
| Web | **Next.js 15 + Tailwind + Recharts**, output statis | satu orang pegang penuh; deploy Vercel sekali klik |
| Orkestrasi | **GitHub Actions cron** | konfigurasi schedule terlihat di repo, log ber-timestamp jadi bukti `[T5]` |
| Kualitas | `pytest`, `ruff`, pre-commit | tes probe + tes pagar agen = bukti "bukan dipalsukan" |
| Deploy | Vercel (web) | nol backend runtime yang bisa mati saat penjurian |

**Sengaja TIDAK dipakai:** LangChain/CrewAI/AutoGen (menyembunyikan justru bagian yang dinilai Track 1), Postman/curl manual (melewati ledger), Postgres, Redis, message queue, auth.

---

## 9. Struktur Repositori

```
sectors2026/
├── README.md                  ← etalase juri: diagram, tabel endpoint, quickstart, dua angka
├── ARCHITECTURE.md · RESEARCH.md · TASK.md · SUBMISSION.md
├── Makefile                   ← make demo | investigate | pipeline | credits | eval | test
│
├── core/
│   ├── sectors/
│   │   ├── client.py          ← CreditAwareClient: gateway tunggal, dua transport
│   │   ├── transport_rest.py  ← httpx
│   │   ├── transport_mcp.py   ← klien MCP tulis sendiri, tiap tool call termeter
│   │   ├── routing.py         ← tabel endpoint → transport  [AD-7]
│   │   ├── catalog.py         ← katalog tool MCP + harga kredit, disajikan ke perencana
│   │   └── schemas.py         ← model pydantic tiap respons
│   ├── ingest/
│   │   ├── tier1_market.py    ← sapuan market-wide harian
│   │   └── backfill.py        ← tarikan historis untuk kalibrasi
│   ├── probes/                ← ALAT AGEN, deterministik, tertes
│   │   ├── base.py            ← kontrak Probe: biaya, jalankan, entri bukti
│   │   ├── broker.py  volume.py  fundamental.py
│   │   ├── freefloat.py  foreign.py  structural.py
│   │   └── registry.py        ← definisi tool yang diekspos ke LLM
│   ├── agent/                 ← ★ INTI TRACK 1
│   │   ├── planner.py         ← rencana penyelidikan dari sinyal Tier-1 + memori
│   │   ├── investigator.py    ← loop: eksekusi → evaluasi → rute ulang → berhenti
│   │   ├── adjudicator.py     ← buku bukti → skor deterministik → narasi
│   │   ├── budget.py          ← pagu kredit & langkah, penolakan eskalasi
│   │   ├── guardrails.py      ← skema, batas langkah, timeout, penutupan aman
│   │   ├── memory.py          ← riwayat investigasi per-ticker, komputasi delta
│   │   └── transcript.py      ← format transkrip yang bisa diputar ulang
│   ├── scoring/
│   │   ├── composite.py       ← pembobotan + band + tingkat keyakinan
│   │   └── facts.py           ← buku bukti: nilai + endpoint + params + as_of
│   ├── narrative/validate.py  ← tolak narasi yang angkanya tidak ada di buku bukti
│   └── export/to_json.py      ← tulis web/public/data/ + runs/
│
├── data/
│   ├── cache/                 ← gitignored
│   ├── warehouse/*.parquet    ← DI-COMMIT: juri jalan tanpa API key
│   ├── memory.duckdb          ← DI-COMMIT: riwayat investigasi
│   └── credit_ledger.jsonl    ← DI-COMMIT: bukti disiplin kredit
│
├── runs/
│   ├── YYYY-MM-DD/run.log · watchlist.json      ← bukti cron otonom
│   └── investigations/<sym>-<tgl>.json          ← transkrip bisa diputar ulang
│
├── evals/
│   ├── agent_eval.py          ← agen vs menyeluruh vs urutan tetap vs acak
│   └── cases.yaml             ← ticker uji + putusan yang diharapkan
├── notebooks/calibration.ipynb
├── reports/validation.md      ← DUA ANGKA yang dikutip di video
├── tests/                     ← probe, pagar agen, validator sitasi
│
├── web/app/(investigasi|papan|metodologi)/
├── .github/workflows/daily.yml
└── video/script-judging.md · script-teaser.md   ← DITULIS SEBELUM COMMIT PERTAMA
```

---

## 10. Kontrak Data Internal

```jsonc
// EvidenceEntry — satu entri per angka yang boleh muncul di narasi
{
  "id": "bci.top3_share",
  "label": "Pangsa net buy 3 broker teratas",
  "value": 0.78, "display": "78%",
  "probe": "broker_concentration",
  "source_endpoint": "fetch-broker-summary-top",
  "source_params": { "symbol": "XXXX", "start": "2026-09-01", "end": "2026-09-05" },
  "as_of": "2026-09-05T17:30:00+07:00",
  "credits_spent": 4
}
```

```jsonc
// InvestigationTranscript — payload halaman investigasi
{
  "symbol": "XXXX", "as_of": "2026-09-05",
  "plan": { "hypotheses": [ /* … */ ], "credit_budget_requested": 12 },
  "steps": [ { "step": 1, "probe": "volume_anomaly", "finding": "confirmed",
               "next_action": "continue", "reason": "…", "credits_spent": 2 } ],
  "evidence": [ /* EvidenceEntry[] */ ],
  "pantau_score": 74, "band": "waspada",
  "confidence": 0.83,                    // bobot komponen yang tercakup
  "credits_total": 11,
  "baseline_credits": 24,                // biaya investigasi menyeluruh
  "narrative": "…",
  "disclaimer": "PANTAU adalah alat informasi dan analisis, bukan saran investasi."
}
```

Validator: setiap token angka dalam `narrative` wajib punya padanan di `evidence`. Gagal → template deterministik. `[AD-4]`

---

## 11. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| **Agen tidak mengalahkan urutan tetap di eval** | **Tinggi** — klaim utama runtuh | Ablasi dijalankan **sebelum** F6, bukan di akhir. Kalau kalah: perkaya sinyal Tier-1 yang diberikan ke perencana; kalau tetap kalah, ubah klaim jadi kualitatif (kemampuan eskalasi & delta memori) dan jangan sebut angka penghematan `[T7]` |
| Kredit habis sebelum kalibrasi selesai | Fatal | Pagu per fase ditegakkan di kode; cache permanen; backfill dijalankan lebih dulu `[AD-3][AD-5]` |
| Himpunan suspensi terlalu kecil | Sedang | Label sekunder (lonjakan volume ekstrem + pembalikan tajam); batasan diakui terbuka |
| `fetch-broker-summary-top` terlalu dangkal untuk HHI | Tinggi | **Spike hari-1** memverifikasi bentuk respons semua endpoint kritis sebelum probe ditulis |
| LLM mengarang angka | Fatal (kredibilitas) | Skor tidak pernah dari LLM `[AD-4]`; validator sitasi; tes dengan buku bukti dipalsukan |
| Agen ngelantur / loop tak berujung | Sedang | Pagar keras `[AD-6]`: 8 langkah, 25 kredit, timeout, satu probe sekali |
| Demo agen gagal saat direkam | Tinggi | Web memutar transkrip tersimpan, nol pemanggilan LLM live `[AD-1]` |
| Dianggap memberi saran finansial | Fatal (diskualifikasi) | Larangan kosakata di CI, **termasuk pada narasi LLM tersimpan** |
| Track 1 paling padat pesaing | Sedang | Diferensiasi bukan "ada agen", tapi **agen yang alasan keberadaannya terukur** (§1, §6 Angka 2) |
| Kelewat deadline / kelengkapan | Fatal | Feature freeze 25 Sep, submit 29 Sep `[T15]`, `SUBMISSION.md` |
| Overscope | Tinggi | Skrip video ditulis lebih dulu = spec `[T2]` |

---

## 12. Definition of Done

Di mesin bersih **tanpa API key**:

```bash
git clone <repo> && cd sectors2026 && make demo
```

→ aplikasi terbuka, memutar ulang investigasi nyata langkah demi langkah, memperlihatkan rencana agen, keputusan perutean di tiap langkah, momen eskalasi, buku bukti tersitasi, skor + tingkat keyakinan, dan halaman Metodologi berisi **dua angka validasi**.

Dengan API key sendiri:

```bash
make investigate SYMBOL=XXXX      # agen sungguhan berjalan, kredit tercatat
make eval                          # agen vs menyeluruh vs urutan tetap vs acak
```

Dan `runs/` memuat **≥10 hari bursa berturut-turut** investigasi yang dijalankan cron tanpa disentuh manusia. `[T5][T7]`
