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

### Pembagian bertiga — kode saja

Tim bertiga. **Tugas di file per-orang mencakup kodenya sekaligus QA-nya sendiri.**
Submission dan video dikerjakan bareng di akhir, jadi tidak ada lajur khusus untuk itu.

| Orang | Lajur | File tugas | Direktori yang dimiliki |
| --- | --- | --- | --- |
| **Melco** | Data, Transport & Probe | [`TASK_MELCO.md`](TASK_MELCO.md) | `core/sectors/` · `core/ingest/` · `core/probes/` · `data/` · `.github/` · `Makefile` |
| **Hamzah** | Agen, Skoring & Eval | [`TASK_HAMZAH.md`](TASK_HAMZAH.md) | `core/agent/` · `core/scoring/` · `core/narrative/` · `evals/` · `notebooks/` |
| **Nadhilla** | Web & Lapisan Ekspor | [`TASK_NADHILLA.md`](TASK_NADHILLA.md) | `web/` · `core/export/` · `fixtures/` |

**Aturan kepemilikan:** jangan pernah mengedit berkas di luar direktori lu. Kalau butuh perubahan
di sana, minta pemiliknya — jangan edit sendiri. Ini yang membuat tiga agen AI bisa jalan
bersamaan tanpa saling menimpa.

**Branch:** `feat/<nama>/<topik>`, merge ke `main` **setiap hari**. Direktori disjoint, jadi
konflik seharusnya nyaris tidak ada — kalau sering konflik, berarti batas kepemilikan bocor.

### Sesi bareng hari ini (8 Sep) — memblokir semua lajur

Satu jam bertiga, sekali saja. Tanpa ini tidak ada yang bisa jalan paralel.

- [ ] Bekukan **lima kontrak** di `contracts/`: `ProbeResult`, `EvidenceEntry`,
      `InvestigationTranscript`, skema tabel warehouse, entri katalog tool
      (bentuknya sudah ada di `ARCHITECTURE.md` §10 — tinggal ditulis jadi skema)
- [ ] Commit **fixture** supaya tidak ada yang menunggu siapa pun:
      `fixtures/transcripts/{normal,waspada,eskalasi}.json` · `fixtures/warehouse-mini/` ·
      `core/probes/stubs.py` (probe palsu yang mengembalikan data kalengan)
- [ ] Sepakati: **kontrak hanya boleh berubah kalau bertiga setuju.** Setelah 12 Sep, beku total.

# Fase Bareng — Kickoff

## F0 — Fondasi & Verifikasi Asumsi · Min 6 – Sen 7 Sep

Jangan bangun apa pun sebelum F0 tuntas.

### Administrasi (blokir semua hal lain)
- [ ] **Bertiga** Tunjuk representative (pemegang kredit & penerima hadiah)
- [ ] **Semua** Buat akun sectors.app dan **selesaikan onboarding penuh** — diverifikasi panitia
- [ ] **Melco** Daftarkan tim di portal hackathon
- [ ] **Melco** Klaim 1.000 kredit API — ⚠️ **klaim mengunci roster permanen**
- [ ] **Melco** Repo `sectors2026` jadikan **publik** (rules mewajibkan, dan wajib tetap publik ≥90 hari)
- [ ] **Melco** API key di GitHub Secrets + `.env` lokal; `.env` sudah di `.gitignore` ✅
- [ ] **Melco** Gabung Slack resmi; **tanyakan di `#discussion` apakah track masih bisa diubah setelah registrasi** — jawabannya dicatat di sini, apa pun hasilnya

### Spike verifikasi endpoint — anggaran maks 40 kredit
Membuktikan enam probe benar-benar bisa dihitung dari data nyata. Kalau gagal, desain diubah **sekarang**.
- [ ] **Melco** Panggil sekali dan simpan respons mentah ke `spikes/`:
      `fetch-close`, `fetch-broker-summary-top`, `fetch-foreign-flow`, `fetch-free-float`,
      `fetch-suspensions`, `fetch-filings`, `fetch-daily-transaction`, `fetch-company-report`
- [ ] **Melco** Catat biaya kredit **aktual** tiap endpoint → `docs/endpoint-costs.md` (dipakai perencana agen untuk menganggarkan)
- [ ] **Melco** Sambungkan klien MCP sekali ke `https://sectors-mcp.supertype.ai/mcp`, dump katalog tool → `docs/mcp-catalog.md`; bandingkan biaya MCP vs REST untuk endpoint yang sama
- [ ] **Hamzah** Konfirmasi: (a) `fetch-suspensions` memuat alasan yang bisa disaring jadi label? (b) `fetch-broker-summary-top` memberi cukup broker untuk HHI? (c) `fetch-free-float` mencakup small cap, bukan cuma LQ45? (d) `fetch-close` benar-benar mengembalikan seluruh ticker dalam satu panggilan?
- [ ] **Hamzah** **Gerbang keputusan:** (a) atau (b) gagal → §Rencana Cadangan sebelum lanjut

### Skrip video (sebelum kode) `[T2]`
- [ ] `video/script-judging.md` mengikuti template 3 menit di `RESEARCH.md` §5
- [ ] Pastikan skrip memuat **keempat perilaku agentik** yang dituntut Track 1: perutean adaptif, penghentian dini, eskalasi, memori. `ARCHITECTURE.md` §3
- [ ] `video/script-teaser.md` (60 detik)
- [ ] Problem statement 1 kalimat, dikunci
- [ ] **Semua** Baca bareng. Fitur di luar skrip dicoret dari rencana.

### Kerangka repo
- [ ] **Melco** Struktur direktori sesuai `ARCHITECTURE.md` §9, `Makefile`, `ruff`, `pytest`, pre-commit
- [ ] **Melco** CI: lint + test + **larangan kosakata** (grep "beli", "jual", "target harga", "rekomendasi" pada seluruh string output **termasuk narasi LLM tersimpan**) `[K5]`

---

## Lajur kode — paralel, lihat file masing-masing

Setelah F0, tiga lajur jalan **bersamaan**. Checklist detailnya ada di file per-orang; di sini
hanya peta dan saling-ketergantungannya. **Jangan menyalin checklist ke sini** — satu sumber kebenaran.

| Lajur | File | Isi | Puncak beban |
| --- | --- | --- | --- |
| Data, Transport & Probe | [`TASK_MELCO.md`](TASK_MELCO.md) | `CreditAwareClient`, REST + MCP, ingest, enam probe, warehouse, cron, CI | 8–14 Sep |
| Agen, Skoring & Eval | [`TASK_HAMZAH.md`](TASK_HAMZAH.md) | kalibrasi bobot, perencana/penyelidik/penilai, memori, pagar, narasi, ablasi | 11–21 Sep |
| Web & Lapisan Ekspor | [`TASK_NADHILLA.md`](TASK_NADHILLA.md) | halaman investigasi, buku bukti, papan waspada, metodologi, ekspor JSON | 10–22 Sep |

### Cara ketiganya tidak saling menunggu

```
Melco  ──probe asli──────────────►  Hamzah
  ▲                                   │
  │                            transkrip asli
warehouse                             │
  │                                   ▼
  └──────────────────────────────►  Nadhilla

Sebelum yang asli datang, semua orang jalan di atas:
  stubs.py  ·  fixtures/warehouse-mini/  ·  fixtures/transcripts/*.json
```

Melco menyerahkan probe asli satu per satu mulai **10 Sep**; Hamzah menyerahkan transkrip asli
sekitar **18 Sep**. Sampai saat itu, stub dan fixture adalah cara kerja yang sah — **bukan darurat.**

### Gerbang lintas-lajur

| Tanggal | Gerbang | Pemilik |
| --- | --- | --- |
| 9 Sep | Bentuk data terverifikasi, atau rencana cadangan dijalankan | Melco |
| 10 Sep | Satu probe hijau + tiga fixture beku + Vercel hidup | Melco, Nadhilla |
| 12 Sep | Warehouse terisi · enam probe hijau · **Angka 1** ada | Melco, Hamzah |
| **14 Sep** | 🔴 **Cron hidup** — jam bukti otonom mulai berdetak | Melco |
| 18 Sep | `make investigate` jalan end-to-end | Hamzah |
| **21 Sep** | 🔴 **Angka 2** ada — atau klaim diubah hari itu juga | Hamzah |
| 22 Sep | Produk end-to-end pakai transkrip asli, ter-deploy | Nadhilla |

---

# Fase Bareng

Dikerjakan bertiga, bukan per-lajur.

## B1 — Bukti Pemakaian Nyata · Sen 22 – Kam 24 Sep `[T6][T13]`

Penyumbang terbesar untuk kriteria 40%. Jangan dikorbankan demi fitur.

- [ ] Rekrut **5–10 investor ritel IDX asli** (grup Telegram/Discord saham, teman kampus, komunitas)
- [ ] Sesi 15 menit: minta mereka menyelidiki saham yang benar-benar sedang mereka pertimbangkan
- [ ] Catat kutipan verbatim + izin tertulis memakai nama/suara di video
- [ ] Rekam 2–3 reaksi asli untuk dipotong ke video
- [ ] Perbaiki hanya masalah yang muncul **berulang**; sisanya ke `reports/feedback.md`

---

## B2 — Polish & Feature Freeze · Rab 24 – **Jum 25 Sep**

- [ ] **Bertiga** Uji `git clone` bersih → `make demo` di mesin lain, **tanpa API key** `[T7]`
- [ ] **Nadhilla** Buang setiap fitur yang pernah goyah di depan kamera `[T9]`
- [ ] **Melco** README etalase juri: diagram, **tabel endpoint Sectors + transport + alasan tiap panggilan**, dua angka validasi, quickstart
- [ ] **Melco** README memuat **tabel bukti rekayasa** `ARCHITECTURE.md` AD-8 — tiap baris tertaut langsung ke berkasnya, supaya juri tidak perlu mencari `[T7]`
- [ ] **Melco** Audit keamanan: nol API key di **seluruh riwayat git** (`git log -p --all | grep`)
- [ ] **Melco** Verifikasi `runs/` ≥10 hari bursa berturut-turut
- [ ] 🔒 **FEATURE FREEZE Jumat 25 Sep, 23:59**

---

## B3 — Produksi Video · Sab 26 – Min 27 Sep

- [ ] Siapkan data & state sebelumnya; nol pemuatan lambat di kamera `[T9]`
- [ ] Rekam **3–4 take**; jangan percepat audio
- [ ] **Judging video ≤3:00** sesuai `RESEARCH.md` §5 — problem + audiens di 15 detik pertama; **tunjukkan agen berpikir**: rencana, satu momen eskalasi, satu penghentian dini; sebut dua angka validasi; tampilkan cron + log ber-timestamp; kutipan pengguna asli; disclaimer di layar; frame terakhir nama + track + URL repo
- [ ] **Teaser 1:00** — potongan terpisah, bertakarir, jalan tanpa suara
- [ ] Subtitle
- [ ] Unggah ≥24 jam sebelum deadline; verifikasi dari **incognito** `[T15]`

---

## B4 — Submission · Sen 28 – **Sel 29 Sep**

- [ ] Jalankan `SUBMISSION.md` sampai habis
- [ ] Post sosmed men-tag akun resmi Sectors
- [ ] **Submit Selasa 29 Sep** — buffer 1 hari. Submit membekukan repo **seketika** `[K3]`
- [ ] Setelah submit: **jangan sentuh repo.** Satu commit = diskualifikasi

---

## Kalender

```
Sep  6-7    F0 — daftar, onboard, klaim kredit, spike, skrip video, repo jadi publik
            ⚠️ kalau belum tuntas, ini pekerjaan hari ini — F0 memblokir semuanya
Sep  8 Sel  Tiga lajur kode mulai paralel — lihat file per-orang
Sep 10 Kam  Melco serahkan probe pertama · Nadhilla bekukan fixture
Sep 11 Jum  ⚠️ BATAS: transport MCP jalan, atau putuskan REST-only
Sep 11 Kam  Hamzah mulai agen
Sep 12 Sab  ✅ GERBANG: Angka 1 ada di reports/validation.md
Sep 14 Sen  ✅ GERBANG KERAS: cron HIDUP — jam bukti mulai berdetak
Sep 18 Kam  Hamzah serahkan transkrip asli ke Nadhilla
Sep 18 Kam  ✅ GERBANG: make investigate jalan end-to-end
Sep 19 Jum  Hamzah eval agen + ablasi
Sep 21 Min  ✅ GERBANG KERAS: Angka 2 ada — atau klaim diubah hari itu juga
Sep 22 Sel  ⚠️ REGISTRASI TUTUP 23:59 WIB (harusnya beres sejak Sep 7)
Sep 22 Sel  B1 user testing dengan investor ritel asli (bertiga)
Sep 25 Jum  🔒 FEATURE FREEZE (B2)
Sep 26 Sab  B3 rekaman video (bertiga)
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
