# TASK.md — Rencana Eksekusi PANTAU

**Hari ini: Selasa, 8 September 2026. Sisa 22 hari.**

> ⚠️ **Kalender di bawah disusun dengan asumsi mulai 6 Sep — kita sudah tertinggal 2 hari.**
> Dua gerbang keras (cron 14 Sep, ablasi 21 Sep) **tidak digeser**, karena keduanya terikat
> deadline nyata, bukan tanggal mulai kita. Selisihnya diambil dari F1–F2, bukan dari video.
Deadline submission: **Rabu, 30 September 2026, 23:59 WIB** — target internal **Selasa 29 September**.
Track: **1 — AI Agents & Assistants**.

Referensi: `ARCHITECTURE.md` (desain), `RESEARCH.md` (alasan). Tanda `[Tn]` = taktik di `RESEARCH.md` §3.

---

## Aturan main tim

1. **Skrip video adalah spec.** Ditulis di F0, sebelum baris kode pertama. Apa pun yang tidak muncul di skrip **tidak dibangun**. `[T2][T1]`
2. **Pipeline cron hidup paling lambat Senin 14 September.** Kita butuh ≥10 hari bursa artefak `runs/` yang di-commit tanpa disentuh manusia. Tanpa ini bukti "not faked" hilang. `[T5]`
3. **Ablasi agen dijalankan paling lambat Minggu 21 September** — bukan di akhir. Kalau agen tidak mengalahkan urutan tetap, klaim utama kita runtuh dan kita perlu waktu untuk mengubah cerita. `ARCHITECTURE.md` §11
4. **Satu orang memegang UI + video sejak hari pertama**, tidak disambi. `[T8]`
5. **Kredit tidak boleh dibelanjakan tanpa lewat `CreditAwareClient`.** Nol `curl` manual, nol Postman. `[AD-5]`
6. **Feature freeze Jumat 25 September.** Setelah itu hanya bugfix, konten, video.
7. Commit kecil dan sering — commit history dibaca juri. `[T7]`

### Peran

| Kode | Peran | Kepemilikan |
| --- | --- | --- |
| **A** | Data & Ingestion | `core/sectors/`, `core/ingest/`, `core/probes/`, warehouse, anggaran kredit, GitHub Actions |
| **B** | Agen & Validasi | `core/agent/`, `core/scoring/`, `evals/`, notebook kalibrasi, `reports/validation.md` |
| **C** | Produk & Video | `web/`, `video/`, halaman Metodologi, user testing, rekaman |
| **D** | Narrative & QA | `core/narrative/`, validator sitasi, pagar agen, CI larangan kosakata, `SUBMISSION.md` |

> **Tim < 4 orang:** gabungkan D ke B. Kalau bertiga, C tetap tidak boleh disambi — potong scope memori agen (§Rencana Cadangan), bukan potong video.

---

## F0 — Fondasi & Verifikasi Asumsi · Min 6 – Sen 7 Sep

Jangan bangun apa pun sebelum F0 tuntas.

### Administrasi (blokir semua hal lain)
- [ ] **A** Bentuk tim final (1–4 orang), tunjuk representative
- [ ] **Semua** Buat akun sectors.app dan **selesaikan onboarding penuh** — diverifikasi panitia
- [ ] **A** Daftarkan tim di portal hackathon
- [ ] **A** Klaim 1.000 kredit API — ⚠️ **klaim mengunci roster permanen**
- [ ] **A** Repo `sectors2026` jadikan **publik** (rules mewajibkan, dan wajib tetap publik ≥90 hari)
- [ ] **A** API key di GitHub Secrets + `.env` lokal; `.env` sudah di `.gitignore` ✅
- [ ] **A** Gabung Slack resmi; **tanyakan di `#discussion` apakah track masih bisa diubah setelah registrasi** — jawabannya dicatat di sini, apa pun hasilnya

### Spike verifikasi endpoint — anggaran maks 40 kredit
Membuktikan enam probe benar-benar bisa dihitung dari data nyata. Kalau gagal, desain diubah **sekarang**.
- [ ] **A** Panggil sekali dan simpan respons mentah ke `spikes/`:
      `fetch-close`, `fetch-broker-summary-top`, `fetch-foreign-flow`, `fetch-free-float`,
      `fetch-suspensions`, `fetch-filings`, `fetch-daily-transaction`, `fetch-company-report`
- [ ] **A** Catat biaya kredit **aktual** tiap endpoint → `docs/endpoint-costs.md` (dipakai perencana agen untuk menganggarkan)
- [ ] **A** Sambungkan klien MCP sekali ke `https://sectors-mcp.supertype.ai/mcp`, dump katalog tool → `docs/mcp-catalog.md`; bandingkan biaya MCP vs REST untuk endpoint yang sama
- [ ] **B** Konfirmasi: (a) `fetch-suspensions` memuat alasan yang bisa disaring jadi label? (b) `fetch-broker-summary-top` memberi cukup broker untuk HHI? (c) `fetch-free-float` mencakup small cap, bukan cuma LQ45? (d) `fetch-close` benar-benar mengembalikan seluruh ticker dalam satu panggilan?
- [ ] **B** **Gerbang keputusan:** (a) atau (b) gagal → §Rencana Cadangan sebelum lanjut

### Skrip video (sebelum kode) `[T2]`
- [ ] **C** `video/script-judging.md` mengikuti template 3 menit di `RESEARCH.md` §5
- [ ] **C** Pastikan skrip memuat **keempat perilaku agentik** yang dituntut Track 1: perutean adaptif, penghentian dini, eskalasi, memori. `ARCHITECTURE.md` §3
- [ ] **C** `video/script-teaser.md` (60 detik)
- [ ] **C** Problem statement 1 kalimat, dikunci
- [ ] **Semua** Baca bareng. Fitur di luar skrip dicoret dari rencana.

### Kerangka repo
- [ ] **A** Struktur direktori sesuai `ARCHITECTURE.md` §9, `Makefile`, `ruff`, `pytest`, pre-commit
- [ ] **D** CI: lint + test + **larangan kosakata** (grep "beli", "jual", "target harga", "rekomendasi" pada seluruh string output **termasuk narasi LLM tersimpan**) `[K5]`

---

## F1 — Lapisan Data & Probe · Sen 7 – Rab 9 Sep · **A**

- [ ] `core/sectors/client.py` — `CreditAwareClient`: gateway tunggal, cache disk permanen berkunci hash, ledger `jsonl`, pagu per fase yang **menolak**, retry + backoff, redaksi key di log `[AD-3][AD-5]`
- [ ] `transport_rest.py` + **`transport_mcp.py` (klien MCP tulis sendiri)** — tiap tool call MCP tercegat dan termeter seperti REST `[AD-7]`
- [ ] `routing.py` — tabel endpoint → transport; keputusan transport **tidak pernah** diserahkan ke LLM
- [ ] `catalog.py` — katalog tool MCP **beserta harga kredit**, disajikan ke perencana agen. Ini yang membuat pemilihan tool jadi sadar biaya `[AD-7]`
- [ ] `schemas.py` (pydantic, dari respons spike)
- [ ] `core/ingest/tier1_market.py` — sapuan market-wide, target **≤6 kredit/hari**
- [ ] `core/probes/base.py` — kontrak `Probe`: `cost_estimate()`, `run()`, `→ (sub_skor, EvidenceEntry[])`
- [ ] Enam probe: `broker`, `volume`, `fundamental`, `freefloat`, `foreign`, `structural`
- [ ] `core/probes/registry.py` — definisi tool yang diekspos ke LLM (nama, deskripsi, skema argumen, biaya)
- [ ] DuckDB warehouse; `make credits`
- [ ] **Tes:** cache hit tidak menambah ledger; pagu terlampaui → raise; tiap probe jalan pada data snapshot tanpa jaringan

> Probe harus bisa dipanggil **tanpa agen sama sekali**. Ini yang membuat lapisan bawah tertes dan agen bisa diablasi.

> ⚠️ **Urutan kerja F1 penting.** AD-7 menambah empat berkas ke fase yang jendelanya sudah
> sempit dan dipegang satu orang. Kerjakan dalam urutan ini, dan **jangan** mulai transport MCP
> sebelum jalur REST end-to-end hijau:
> 1. `client.py` + `transport_rest.py` + `schemas.py` → satu probe jalan penuh
> 2. Lima probe sisanya + `tier1_market.py` → **F2 sudah bisa dimulai di sini**
> 3. `transport_mcp.py` + `routing.py` + `catalog.py`
>
> Langkah 3 adalah **peningkatan, bukan prasyarat**. Rubrik berbunyi "Sectors API *or* MCP" —
> REST-only tetap lolos. Kalau langkah 3 belum jalan pada **11 Sep**, lihat §Rencana Cadangan.

---

## F2 — Backfill & Kalibrasi Bobot · Rab 9 – Sab 12 Sep · **A + B** · anggaran 400 kredit

- [ ] **A** `core/ingest/backfill.py` — 120 hari bursa `fetch-close`; suspensi & filings 24 bulan; Tier-2 untuk positif + kontrol
- [ ] **B** Himpunan positif dari `fetch-suspensions` (saring alasan pergerakan/aktivitas tidak wajar)
- [ ] **B** Himpunan kontrol tersamakan (kapitalisasi + subsektor)
- [ ] **B** Enam sub-skor pada T-1/T-3/T-5/T-10 — **strictly point-in-time, nol lookahead**
- [ ] **B** Cari bobot; split waktu 18 bulan kalibrasi / 6 bulan uji
- [ ] **B** `reports/validation.md` **Angka 1** — Precision@20, recall pada ambang 60, median lead time, plus **batasan yang diakui terbuka** `[T6][T7]`

---

## F3 — Skoring & Pipeline Hidup · Kam 10 – **Sen 14 Sep** · **B + A**

> ⚠️ **Tenggat keras 14 September.** Jam bukti operasi otonom mulai berdetak.

- [ ] **B** `core/scoring/composite.py` — pembobotan F2, band, **tingkat keyakinan** (bobot komponen yang tercakup) `ARCHITECTURE.md` §4
- [ ] **B** `core/scoring/facts.py` — buku bukti sesuai kontrak `ARCHITECTURE.md` §10
- [ ] **A** `core/export/to_json.py` → `web/public/data/` + `runs/`
- [ ] **A** `.github/workflows/daily.yml` — cron **10:30 UTC = 17:30 WIB**, Sen–Jum
      - Tahap 1 (mulai 14 Sep): sapuan Tier-1 + watchlist deterministik → commit `runs/YYYY-MM-DD/`
      - Tahap 2 (mulai ±19 Sep): agen menyelidiki sendiri top-N → commit `runs/investigations/`
- [ ] **A** Verifikasi eksekusi cron pertama yang benar-benar tak disentuh manusia; screenshot konfigurasi schedule untuk video `[T5]`
- [ ] **A** Commit `data/warehouse/*.parquet` supaya juri jalan tanpa API key `[AD-2]`

---

## F4 — Agen · Kam 11 – Kam 18 Sep · **B + D** · ★ inti Track 1

Fase terpenting. Ini yang dinilai juri sebagai "custom agent logic or orchestration".

- [ ] **B** `agent/planner.py` — dari sinyal Tier-1 + memori → hipotesis, probe terurut, permintaan pagu kredit. Keluaran **JSON terstruktur**, bukan prosa
- [ ] **B** `agent/investigator.py` — loop eksekusi → evaluasi temuan → `continue` / `escalate` / `conclude`
- [ ] **B** `agent/budget.py` — pagu per-investigasi (25 kredit) & per-hari; eskalasi bisa **ditolak**, dan agen harus menyimpulkan dengan bukti seadanya
- [ ] **D** `agent/guardrails.py` — maks 8 langkah, timeout per langkah, validasi skema, satu probe sekali per investigasi, penutupan aman saat pagar tertembus `[AD-6]`
- [ ] **B** `agent/memory.py` — riwayat per-ticker di DuckDB; investigasi ulang menghasilkan rencana berbeda yang diarahkan ke perubahan
- [ ] **B** `agent/transcript.py` — format transkrip yang bisa diputar ulang `ARCHITECTURE.md` §10
- [ ] **B** `agent/adjudicator.py` — buku bukti → skor **deterministik** → narasi LLM
- [ ] **D** `narrative/validate.py` — tiap token angka wajib ada padanannya di buku bukti; gagal → template deterministik `[AD-4]`
- [ ] **Tes:** buku bukti dipalsukan → validator menolak; agen ngelantur → pagar menutup dengan aman; pagu habis → tetap menghasilkan putusan berkeyakinan rendah, bukan crash
- [ ] **B** `make investigate SYMBOL=XXXX` jalan end-to-end

---

## F5 — Eval Agen · Jum 19 – **Min 21 Sep** · **B** · anggaran 130 kredit

> ⚠️ **Gerbang keras.** Kalau agen tidak mengalahkan urutan tetap, kita ubah klaim **sekarang**, bukan saat merekam video.

- [ ] `evals/cases.yaml` — 30–50 ticker uji: campuran normal, mencurigakan, dan yang benar-benar pernah disuspend
- [ ] `evals/agent_eval.py` — empat jalur: **agen** vs **menyeluruh** vs **urutan tetap** vs **acak berpagu sama**
- [ ] Ukur: kredit per investigasi, kesepakatan band vs menyeluruh, presisi eskalasi
- [ ] **Ukur juga pemilihan tool sadar biaya** `[AD-7]` — ketika perencana melihat katalog MCP
      **beserta harganya**, apakah ia memilih tool yang lebih murah untuk keyakinan yang setara?
      Bandingkan dengan katalog yang harganya disembunyikan. Ini yang membuktikan klaim MCP kita,
      bukan sekadar "kami memakai MCP"
- [ ] `reports/validation.md` **Angka 2** — target penghematan kredit ≥50% dengan kesepakatan band ≥90%
- [ ] Kunci satu kalimat untuk video: *"investigasi menyeluruh butuh N kredit; perencana kami rata-rata Y, dan sepakat Z% dari waktu"*
- [ ] Kalau target meleset → jalankan mitigasi di `ARCHITECTURE.md` §11 baris pertama

---

## F6 — Web · Sen 14 – Sen 22 Sep · **C**

Dimulai paralel dengan F4 memakai transkrip contoh; disambungkan ke transkrip asli begitu F4 selesai.

- [ ] Next.js 15 + Tailwind, baca **JSON statis saja**, nol panggilan API & LLM runtime `[AD-1]`
- [ ] **Halaman Investigasi** — putar ulang transkrip langkah demi langkah: rencana awal, tiap langkah, temuan, **keputusan perutean agen**, momen eskalasi, penghentian dini. Ini tampilan yang menjual Track 1
- [ ] Skor besar + band + **tingkat keyakinan** + kredit terpakai vs baseline menyeluruh
- [ ] **Buku Bukti** — tiap angka bisa diklik ke endpoint + params + `as-of` `[T12]`
- [ ] **Papan Waspada** — arsip investigasi otonom bertanggal, bisa ditelusuri
- [ ] **Halaman Metodologi** — rumus, bobot, **dua angka validasi**, batasan yang diakui `[T6]`
- [ ] Disclaimer permanen: "PANTAU adalah alat informasi dan analisis, bukan saran investasi." `[K5]`
- [ ] Bahasa Indonesia penuh, format IDR, tanggal WIB `[T14]`
- [ ] Mobile-first — persona kita pegang HP
- [ ] Deploy Vercel; verifikasi dari incognito

---

## F7 — Bukti Pemakaian Nyata · Sen 22 – Kam 24 Sep · **C** `[T6][T13]`

Penyumbang terbesar untuk kriteria 40%. Jangan dikorbankan demi fitur.

- [ ] Rekrut **5–10 investor ritel IDX asli** (grup Telegram/Discord saham, teman kampus, komunitas)
- [ ] Sesi 15 menit: minta mereka menyelidiki saham yang benar-benar sedang mereka pertimbangkan
- [ ] Catat kutipan verbatim + izin tertulis memakai nama/suara di video
- [ ] Rekam 2–3 reaksi asli untuk dipotong ke video
- [ ] Perbaiki hanya masalah yang muncul **berulang**; sisanya ke `reports/feedback.md`

---

## F8 — Polish & Feature Freeze · Rab 24 – **Jum 25 Sep**

- [ ] **Semua** Uji `git clone` bersih → `make demo` di mesin lain, **tanpa API key** `[T7]`
- [ ] **C** Buang setiap fitur yang pernah goyah di depan kamera `[T9]`
- [ ] **A** README etalase juri: diagram, **tabel endpoint Sectors + transport + alasan tiap panggilan**, dua angka validasi, quickstart
- [ ] **A** README memuat **tabel bukti rekayasa** `ARCHITECTURE.md` AD-8 — tiap baris tertaut langsung ke berkasnya, supaya juri tidak perlu mencari `[T7]`
- [ ] **D** Audit keamanan: nol API key di **seluruh riwayat git** (`git log -p --all | grep`)
- [ ] **A** Verifikasi `runs/` ≥10 hari bursa berturut-turut
- [ ] 🔒 **FEATURE FREEZE Jumat 25 Sep, 23:59**

---

## F9 — Produksi Video · Sab 26 – Min 27 Sep · **C**

- [ ] Siapkan data & state sebelumnya; nol pemuatan lambat di kamera `[T9]`
- [ ] Rekam **3–4 take**; jangan percepat audio
- [ ] **Judging video ≤3:00** sesuai `RESEARCH.md` §5 — problem + audiens di 15 detik pertama; **tunjukkan agen berpikir**: rencana, satu momen eskalasi, satu penghentian dini; sebut dua angka validasi; tampilkan cron + log ber-timestamp; kutipan pengguna asli; disclaimer di layar; frame terakhir nama + track + URL repo
- [ ] **Teaser 1:00** — potongan terpisah, bertakarir, jalan tanpa suara
- [ ] Subtitle
- [ ] Unggah ≥24 jam sebelum deadline; verifikasi dari **incognito** `[T15]`

---

## F10 — Submission · Sen 28 – **Sel 29 Sep**

- [ ] Jalankan `SUBMISSION.md` sampai habis
- [ ] Post sosmed men-tag akun resmi Sectors
- [ ] **Submit Selasa 29 Sep** — buffer 1 hari. Submit membekukan repo **seketika** `[K3]`
- [ ] Setelah submit: **jangan sentuh repo.** Satu commit = diskualifikasi

---

## Kalender

```
Sep  6-7    F0 — daftar, onboard, klaim kredit, spike, skrip video, repo jadi publik
            ⚠️ kalau belum tuntas, ini pekerjaan hari ini — F0 memblokir semuanya
Sep  8 Sel  F1 lapisan data & enam probe (REST dulu, MCP belakangan)
Sep 10 Kam  F2 backfill & kalibrasi bobot — mulai begitu enam probe hijau
Sep 11 Jum  ⚠️ BATAS: transport MCP jalan, atau putuskan REST-only
Sep 11 Kam  F4 agen mulai (paralel dengan F3)
Sep 12 Sab  ✅ GERBANG: Angka 1 ada di reports/validation.md
Sep 14 Sen  ✅ GERBANG KERAS: cron HIDUP — jam bukti mulai berdetak
Sep 14 Sen  F6 web mulai (pakai transkrip contoh)
Sep 18 Kam  ✅ GERBANG: make investigate jalan end-to-end
Sep 19 Jum  F5 eval agen + ablasi
Sep 21 Min  ✅ GERBANG KERAS: Angka 2 ada — atau klaim diubah hari itu juga
Sep 22 Sel  ⚠️ REGISTRASI TUTUP 23:59 WIB (harusnya beres sejak Sep 7)
Sep 22 Sel  F7 user testing dengan investor ritel asli
Sep 25 Jum  🔒 FEATURE FREEZE
Sep 26 Sab  F9 rekaman video
Sep 27 Min  Editing + unggah
Sep 29 Sel  🚀 SUBMIT (buffer 1 hari)
Sep 30 Rab  Deadline resmi 23:59 WIB — jangan pakai hari ini
Okt  1–8    Penjurian asinkron
Okt  9      Pengumuman
```

---

## Rencana Cadangan

| Kalau ini gagal | Ganti dengan | Batas keputusan |
| --- | --- | --- |
| `fetch-suspensions` tidak memberi label yang bisa dipakai | Label sekunder: lonjakan volume ekstrem + pembalikan harga tajam dalam 10 hari bursa. Framing jadi "deteksi pola distribusi", inti produk tetap | 9 Sep |
| `fetch-broker-summary-top` terlalu dangkal untuk HHI | Turunkan bobot BCI, naikkan FRD dan SSS. Tetap enam probe | 9 Sep |
| **Agen kalah dari urutan tetap di ablasi** | Perkaya sinyal Tier-1 ke perencana. Kalau tetap kalah: buang klaim penghematan kredit, jual **kemampuan eskalasi dan delta memori** secara kualitatif — keduanya tetap memenuhi syarat Track 1 dan tetap jujur | 21 Sep |
| **Transport MCP bermasalah** (auth, streaming, bentuk respons) | Jalankan **REST-only**. Rubrik menyebut "Sectors API *or* MCP" — bukan keduanya. Buang klaim pemilihan tool sadar biaya dari video; Angka 2 tetap hidup lewat pemilihan probe. **Jangan korbankan F2 demi MCP** | 11 Sep |
| Waktu habis di F4 | Potong **memori agen** lebih dulu (perencana + penyelidik + penilai sudah cukup memenuhi syarat Track 1). Jangan potong web atau video | 18 Sep |
| Anggaran kredit menipis | Persempit alam semesta ke ±80 ticker small/mid cap paling sering muncul di most-traded 90 hari. Persempit cerita, bukan turunkan kualitas | kapan saja |

---

## Papan Skor Mandiri

Dinilai jujur tiap Minggu malam. Rubrik lengkap: `RESEARCH.md` §4.

| Minggu | Gerbang lolos | Usability 40% | Video 30% | Teknis 30% |
| --- | --- | --- | --- | --- |
| 7 Sep | | | | |
| 14 Sep | | | | |
| 21 Sep | | | | |
| 25 Sep | | | | |
