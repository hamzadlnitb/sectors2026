# TASK.md — Rencana Eksekusi PANTAU

**Hari ini: Sabtu, 5 September 2026. Sisa 25 hari.**
Deadline submission: **Rabu, 30 September 2026, 23:59 WIB** — target internal kita **Selasa 29 September**.

Referensi: `ARCHITECTURE.md` (desain), `RESEARCH.md` (alasan). Tanda `[Tn]` = taktik di `RESEARCH.md` §3.

---

## Aturan main tim

1. **Skrip video adalah spec.** Ditulis di F0, sebelum baris kode pertama. Apa pun yang tidak muncul di skrip **tidak dibangun**. `[T2][T1]`
2. **Pipeline harian harus hidup paling lambat Senin 14 September.** Ini bukan target, ini kunci — kita butuh ≥10 hari bursa artefak `runs/` yang di-commit cron sebagai bukti unattended run. Tanpa ini bukti "not faked" hilang. `[T5]`
3. **Satu orang memegang UI + video sejak hari pertama**, tidak disambi. `[T8]`
4. **Kredit tidak boleh dibelanjakan tanpa lewat `CreditAwareClient`.** Tidak ada `curl` manual, tidak ada eksperimen di Postman. `[AD-5]`
5. **Feature freeze Jumat 25 September.** Setelah itu hanya bugfix, konten, dan video.
6. Commit kecil dan sering — commit history dibaca juri. `[T7]`

### Peran

| Kode | Peran | Kepemilikan |
| --- | --- | --- |
| **A** | Data & Ingestion | `core/sectors/`, `core/ingest/`, warehouse, anggaran kredit, GitHub Actions |
| **B** | Scoring & Validasi | `core/scoring/`, notebook kalibrasi, `reports/validation.md`, tes |
| **C** | Produk & Video | `web/`, `video/`, halaman Metodologi, user testing, rekaman |
| **D** | Narrative & QA | `core/narrative/`, validator sitasi, CI larangan kosakata, checklist submission |

> **Tim < 4 orang:** gabungkan D ke B. Kalau bertiga, C tetap tidak boleh disambi — potong scope narrative layer (opsional di Track 3), bukan potong video.

---

## F0 — Fondasi & Verifikasi Asumsi · Sab 5 – Sen 7 Sep

Fase ini menentukan apakah rencana kita realistis. Jangan bangun apa pun sebelum F0 tuntas.

### Administrasi (blokir semua hal lain)
- [ ] **A** Bentuk tim final (1–4 orang), tunjuk representative
- [ ] **Semua** Buat akun sectors.app dan **selesaikan onboarding penuh** — diverifikasi panitia, wajib sebelum kode ditulis
- [ ] **A** Daftarkan tim di portal hackathon
- [ ] **A** Klaim 1.000 kredit API — ⚠️ **klaim mengunci roster permanen**, pastikan komposisi tim final
- [ ] **A** Buat repo GitHub **publik** bernama `pantau`, commit pertama hari ini (bukti tanggal ≥19 Agu) `[T15]`
- [ ] **A** Simpan API key di GitHub Secrets + `.env` lokal; `.env` masuk `.gitignore` sejak commit pertama
- [ ] **A** Gabung Slack resmi, channel `#discussion` dan `#support`

### Spike verifikasi endpoint — anggaran maks 40 kredit
Tujuan: membuktikan enam komponen skor benar-benar bisa dihitung dari data nyata. Kalau ada yang gagal, desain diubah **sekarang**, bukan minggu depan.
- [ ] **A** Panggil sekali dan simpan respons mentah tiap endpoint kritis ke `spikes/`:
      `fetch-close`, `fetch-broker-summary-top`, `fetch-foreign-flow`, `fetch-free-float`,
      `fetch-suspensions`, `fetch-filings`, `fetch-daily-transaction`, `fetch-company-report`
- [ ] **A** Catat biaya kredit **aktual** tiap endpoint → `docs/endpoint-costs.md`
- [ ] **B** Konfirmasi tiap jawaban: (a) `fetch-suspensions` memuat alasan yang bisa disaring jadi label? (b) `fetch-broker-summary-top` memberi cukup broker untuk hitung HHI? (c) `fetch-free-float` mencakup small cap, bukan cuma LQ45? (d) `fetch-close` benar-benar mengembalikan seluruh ticker dalam satu panggilan?
- [ ] **B** **Gerbang keputusan:** kalau (a) atau (b) gagal → eskalasi ke §Rencana Cadangan sebelum lanjut

### Skrip video (sebelum kode) `[T2]`
- [ ] **C** Tulis `video/script-judging.md` mengikuti template 3 menit di `RESEARCH.md` §5
- [ ] **C** Tulis `video/script-teaser.md` (60 detik)
- [ ] **C** Tulis problem statement 1 kalimat dan kunci — tidak boleh berubah lagi
- [ ] **Semua** Baca skrip bareng. Setiap fitur yang tidak muncul di skrip dicoret dari rencana.

### Kerangka repo
- [ ] **A** Struktur direktori sesuai `ARCHITECTURE.md` §8, `Makefile`, `ruff`, `pytest`, pre-commit
- [ ] **D** CI GitHub Actions: lint + test + **larangan kosakata** (grep "beli", "jual", "target harga", "rekomendasi" pada string output) `[K5]`

---

## F1 — Lapisan Data · Sen 8 – Rab 10 Sep · **A**

- [ ] `core/sectors/client.py` — `CreditAwareClient`: cache disk permanen berkunci hash, ledger `jsonl`, pagu per fase yang **menolak** (bukan memperingatkan), retry + backoff, redaksi key di log `[AD-3][AD-5]`
- [ ] `core/sectors/endpoints.py` — wrapper tiap endpoint dengan biaya kredit tercatat di dekorator
- [ ] `core/sectors/schemas.py` — model pydantic dari respons spike F0
- [ ] `core/ingest/tier1_market.py` — sapuan market-wide, target **≤6 kredit/hari**
- [ ] `core/ingest/tier2_deep.py` — pendalaman per-ticker, dibatasi keras 15 ticker/hari
- [ ] DuckDB warehouse + skema tabel; `make credits` mencetak posisi ledger
- [ ] **Tes:** cache hit tidak menambah ledger; pagu terlampaui → raise, bukan warning

---

## F2 — Backfill & Kalibrasi · Rab 10 – Min 13 Sep · **A + B** · anggaran 450 kredit

- [ ] **A** `core/ingest/backfill.py` — 120 hari bursa `fetch-close`; suspensi & filings 24 bulan; Tier-2 untuk himpunan positif + kontrol
- [ ] **B** Bangun himpunan positif dari `fetch-suspensions` (saring alasan terkait pergerakan/aktivitas tidak wajar)
- [ ] **B** Bangun himpunan kontrol tersamakan berdasarkan kapitalisasi + subsektor
- [ ] **B** Hitung 6 sub-skor pada T-1/T-3/T-5/T-10 — **strictly point-in-time, nol lookahead**
- [ ] **B** Cari bobot: logistic regression atau grid search; pilih yang bisa dijelaskan dalam 15 detik
- [ ] **B** Split waktu: kalibrasi 18 bulan pertama, uji 6 bulan terakhir
- [ ] **B** `reports/validation.md` — Precision@20, recall pada ambang 60, **median lead time**, plus **batasan yang diakui terbuka** `[T6][T7]`
- [ ] **B** Kunci satu angka untuk video ("X% presisi, median peringatan Y hari bursa lebih awal")

---

## F3 — Scoring Engine & Pipeline Hidup · Kam 11 – **Sen 14 Sep** · **B + A**

> ⚠️ **Tenggat keras 14 September.** Jam bukti unattended run mulai berdetak di sini.

- [ ] **B** `core/scoring/` — enam komponen (`bci`, `vas`, `pfd`, `ffs`, `frd`, `sss`), fungsi murni, unit test tiap satu + kasus batas (data hilang, ticker baru IPO, ticker tersuspend)
- [ ] **B** `composite.py` — pembobotan hasil F2 + band 0/30/60/80
- [ ] **B** `facts.py` — fact table sesuai kontrak `ARCHITECTURE.md` §9 (nilai + endpoint + params + `as_of`)
- [ ] **A** `core/export/to_json.py` — tulis `web/public/data/` dan `runs/YYYY-MM-DD/`
- [ ] **A** `.github/workflows/daily.yml` — cron **10:30 UTC = 17:30 WIB**, Sen–Jum; commit artefak + `run.log` otomatis
- [ ] **A** Verifikasi eksekusi cron pertama yang benar-benar tak disentuh manusia; screenshot konfigurasi schedule untuk video `[T5]`
- [ ] **A** Commit `data/warehouse/*.parquet` supaya juri bisa jalan tanpa API key `[AD-2]`

---

## F4 — Web · Sen 14 – Min 20 Sep · **C**

- [ ] Next.js 15 + Tailwind, baca **JSON statis saja**, nol panggilan API runtime `[AD-1]`
- [ ] **Halaman Ticker** — skor besar, band, enam komponen sebagai bar, tiap angka **bisa diklik ke sumber** (endpoint + `as_of`) `[T12]`
- [ ] **Papan Waspada** — daftar harian + arsip bertanggal yang bisa ditelusuri (bukti unattended run terlihat *di dalam produk*, bukan cuma di repo)
- [ ] **Halaman Metodologi** — rumus, bobot, hasil validasi, batasan yang diakui `[T6]`
- [ ] Disclaimer permanen: "PANTAU adalah alat informasi dan analisis, bukan saran investasi." `[K5]`
- [ ] Bahasa Indonesia penuh, format IDR, tanggal WIB, kalender bursa `[T14]`
- [ ] Deploy Vercel; verifikasi URL publik dari incognito
- [ ] Mobile-first — persona kita pegang HP, bukan Bloomberg terminal

---

## F5 — Narrative Layer · Kam 17 – Min 20 Sep · **D**

- [ ] `narrative/generate.py` — Claude menyusun 3–4 kalimat Bahasa Indonesia **hanya dari fact table**
- [ ] `narrative/validate.py` — setiap token angka wajib punya padanan di `facts`; gagal → fallback template deterministik `[AD-4]`
- [ ] Kosakata bebas saran finansial; lolos CI larangan kosakata
- [ ] Narasi diprakomputasi dan disimpan sebagai JSON — **tidak ada panggilan LLM saat pengunjung membuka halaman** `[K2]`
- [ ] Tes: fact table dipalsukan → validator menolak

---

## F6 — Bukti Pemakaian Nyata · Sen 21 – Kam 24 Sep · **C** `[T6][T13]`

Ini penyumbang terbesar untuk kriteria 40%. Jangan dikorbankan demi fitur.

- [ ] Rekrut **5–10 investor ritel IDX asli** (grup Telegram/Discord saham, teman kampus, komunitas)
- [ ] Sesi 15 menit: minta mereka cek saham yang benar-benar sedang mereka pertimbangkan
- [ ] Catat kutipan verbatim + izin tertulis memakai nama/suara di video
- [ ] Rekam 2–3 reaksi asli untuk dipotong ke video `[T6 — preseden Medkit]`
- [ ] Perbaiki hanya masalah yang muncul **berulang**; sisanya masuk `reports/feedback.md`, tidak dikerjakan

---

## F7 — Polish & Feature Freeze · Kam 24 – **Jum 25 Sep**

- [ ] **Semua** Uji `git clone` bersih → `make demo` di mesin lain, tanpa API key `[T7]`
- [ ] **C** Buang setiap fitur yang pernah goyah di depan kamera — kelihatan rapi > kelihatan lengkap `[T9]`
- [ ] **A** README etalase juri: diagram arsitektur, **tabel endpoint Sectors + alasan tiap panggilan**, angka validasi, quickstart, ledger kredit `[T7]`
- [ ] **D** Audit keamanan: nol API key di **seluruh riwayat git** (`git log -p | grep`), bukan cuma di HEAD
- [ ] **A** Verifikasi `runs/` berisi **≥10 hari bursa berturut-turut**
- [ ] 🔒 **FEATURE FREEZE Jumat 25 Sep, 23:59** — setelah ini hanya bugfix, konten, video

---

## F8 — Produksi Video · Sab 26 – Min 27 Sep · **C**

- [ ] Siapkan data & state sebelumnya; nol pemuatan lambat di kamera `[T9]`
- [ ] Rekam **3–4 take**, ambil yang terbaik; jangan percepat audio
- [ ] **Judging video ≤3:00** sesuai template `RESEARCH.md` §5 — problem + audiens di 15 detik pertama; workflow end-to-end; **tampilkan konfigurasi cron + log berjalan ber-timestamp**; sebut angka validasi; tampilkan kutipan pengguna asli; disclaimer di layar; frame terakhir memuat nama + track + URL repo
- [ ] **Teaser 1:00** — potongan terpisah, bertakarir, jalan tanpa suara
- [ ] Subtitle. Bahasa Indonesia tidak dipenalti dan terbaca lebih otentik di panel ini `[T14]`
- [ ] Unggah ≥24 jam sebelum deadline; verifikasi keduanya terbuka dari **incognito/logged out** `[T15]`

---

## F9 — Submission · Sen 28 – **Sel 29 Sep**

- [ ] Jalankan `SUBMISSION.md` sampai habis
- [ ] Post sosmed men-tag akun resmi Sectors
- [ ] **Submit Selasa 29 Sep** — buffer 1 hari penuh. Submit membekukan repo **seketika**, tanpa bugfix `[K3]`
- [ ] Setelah submit: **jangan sentuh repo.** Satu commit = diskualifikasi

---

## Kalender

```
Sep  5 Sab  F0 mulai — daftar, onboard, klaim kredit, spike, skrip video
Sep  7 Sen  ✅ GERBANG: spike selesai, skrip video terkunci, repo hidup
Sep  8 Sen  F1 lapisan data
Sep 10 Rab  F2 backfill & kalibrasi
Sep 13 Min  ✅ GERBANG: angka validasi ada di reports/validation.md
Sep 14 Sen  ✅ GERBANG KERAS: pipeline cron HIDUP — jam bukti mulai berdetak
Sep 14 Sen  F4 web mulai
Sep 17 Kam  F5 narrative layer
Sep 20 Min  ✅ GERBANG: produk end-to-end jalan, ter-deploy publik
Sep 21 Sen  F6 user testing dengan investor ritel asli
Sep 22 Sel  ⚠️ REGISTRASI TUTUP 23:59 WIB (harusnya sudah beres sejak Sep 7)
Sep 25 Jum  🔒 FEATURE FREEZE
Sep 26 Sab  F8 rekaman video
Sep 27 Min  Editing + unggah
Sep 29 Sel  🚀 SUBMIT (buffer 1 hari)
Sep 30 Rab  Deadline resmi 23:59 WIB — jangan pakai hari ini
Okt  1–8    Penjurian asinkron
Okt  9      Pengumuman
```

---

## Rencana Cadangan

Dipicu **hanya** oleh gerbang keputusan F0.

| Kalau ini gagal | Ganti dengan |
| --- | --- |
| `fetch-suspensions` tidak memberi label yang bisa dipakai | Label sekunder: lonjakan volume ekstrem diikuti pembalikan harga tajam dalam 10 hari bursa. Framing berubah dari "prediksi suspensi" jadi "deteksi pola distribusi" — inti produk tetap |
| `fetch-broker-summary-top` terlalu dangkal untuk HHI | Turunkan bobot BCI, naikkan FRD (`fetch-foreign-flow`) dan SSS. Skor tetap enam komponen |
| Anggaran kredit menipis lebih cepat dari rencana | Persempit alam semesta ke ±80 ticker small/mid cap yang paling sering muncul di most-traded 90 hari terakhir. Persempit cerita, bukan turunkan kualitas |
| Seluruh pendekatan bandarmology mentok | Beralih ke **arketipe B** di `RESEARCH.md` §3: jembatan aset tambang → ekuitas (izin IUP, produksi, cadangan, ekspor vs valuasi emiten). Data sama uniknya, nol tumpang tindih dengan recipe resmi. **Keputusan ini harus diambil paling lambat 8 Sep** |

---

## Papan Skor Mandiri

Nilai diri jujur setiap Minggu malam. Rubrik lengkap: `RESEARCH.md` §4.

| Minggu | Gerbang lolos | Usability 40% | Video 30% | Teknis 30% |
| --- | --- | --- | --- | --- |
| 7 Sep | | | | |
| 14 Sep | | | | |
| 21 Sep | | | | |
| 25 Sep | | | | |
