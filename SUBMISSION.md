# SUBMISSION.md — Checklist Freeze

> Jalankan dari atas ke bawah pada **Selasa 29 September 2026**.
> Submit membekukan repo **seketika**. Tidak ada bugfix setelahnya. Satu commit pasca-submit = diskualifikasi.
> Banyak tim gugur di gerbang kelengkapan, bukan di kualitas. `RESEARCH.md` §3 [T15]

---

## 1. Gerbang eligibility (pass/fail — panitia mengecek ini sebelum menilai)

- [ ] Semua anggota tim sudah **menyelesaikan onboarding penuh** di sectors.app (bukan sekadar daftar)
- [ ] Repo **publik** dan akan tetap publik ≥90 hari setelah pengumuman
- [ ] Commit pertama bertanggal **≥19 Agustus 2026**; tidak ada kode migrasi dari proyek lama
- [ ] Produk **jalan end-to-end** di mesin bersih: `git clone && make demo`
- [ ] Data Sectors adalah sumber inti — tulis satu kalimat pembuktiannya di README
- [ ] Proyek ini tidak disubmit ke lomba lain

## 2. Keamanan

- [ ] **Nol API key di seluruh riwayat git**, bukan cuma di HEAD:
      `git log -p --all | grep -iE 'sk-|api[_-]?key|bearer|secret'`
- [ ] `.env` ada di `.gitignore` sejak commit pertama
- [ ] Secret hanya hidup di GitHub Secrets / environment Vercel

## 3. Kepatuhan aturan

- [ ] **Nol kode eksekusi order** — tidak ada integrasi broker, tidak ada endpoint order, di mana pun
- [ ] **Nol saran finansial** — CI larangan kosakata hijau ("beli", "jual", "target harga", "rekomendasi", "cuan", "pasti naik")
- [ ] Disclaimer terlihat di setiap halaman produk **dan** di video
- [ ] Tidak ada konten SARA/diskriminatif

## 3b. Gerbang khusus Track 1

- [ ] Ada **orkestrasi agen buatan sendiri**: perencana, loop penyelidik, penilai — bukan prompt di atas klien orang lain
- [ ] Uji anti-diskualifikasi: cabut prompt kami dari klien AI mana pun → perencana, buku bukti, mesin skoring, memori, dan validator sitasi tetap ada di kode kami
- [ ] Keempat perilaku agentik terlihat di transkrip **dan di video**: perutean adaptif, penghentian dini, eskalasi, memori
- [ ] **Skor tidak pernah dihasilkan LLM** — hanya rencana, perutean, dan narasi
- [ ] Narasi LLM tersimpan ikut lolos CI larangan kosakata

## 4. Bukti "bukan dipalsukan untuk demo" (kriteria teknis 30%)

- [ ] `runs/` memuat **≥10 hari bursa berturut-turut** artefak yang di-commit cron tanpa disentuh manusia
- [ ] `data/credit_ledger.jsonl` ter-commit
- [ ] `data/warehouse/*.parquet` ter-commit — juri bisa menjalankan sistem **tanpa API key**
- [ ] `reports/validation.md` memuat **dua angka** (presisi skor + efisiensi perutean agen) + batasan yang diakui terbuka
- [ ] `runs/investigations/` memuat transkrip yang bisa diputar ulang — juri bisa memutar hasil identik berkali-kali
- [ ] `evals/` memuat ablasi: agen vs menyeluruh vs urutan tetap vs acak
- [ ] Tes lolos: `make test`
- [ ] **Tabel bukti rekayasa** di README lengkap dan tiap tautannya hidup (`ARCHITECTURE.md` AD-8)
- [ ] Pemakaian **MCP maupun REST** terdokumentasi, dan keduanya benar-benar tercatat di ledger `[AD-7]`
- [ ] README memuat diagram arsitektur + **tabel endpoint Sectors beserta alasan tiap panggilan**
- [ ] Riwayat commit terbaca sebagai kerja bertahap yang wajar

## 5. Enam deliverable submission

- [ ] **1. Link repo publik** — dibuka dari incognito, berhasil
- [ ] **2. Teaser 1 menit** — screen recording produk berjalan, publik di YouTube/sosmed, **dites logged out**
- [ ] **3. Judging video ≤3:00** — publik/unlisted di YouTube/Vimeo/Drive(sharing on)/Loom, **dites logged out**
      - [ ] Durasi diverifikasi ≤3:00 (bukan 3:04)
      - [ ] Problem + audiens disebut di **15 detik pertama**
      - [ ] Core workflow ditampilkan **end-to-end**, bukan slide
      - [ ] Konfigurasi cron + log berjalan ber-timestamp tampil di layar
      - [ ] **Agen terlihat berpikir**: rencana, satu momen eskalasi, satu penghentian dini
      - [ ] Dua angka validasi disebut
      - [ ] Kutipan pengguna ritel asli tampil
      - [ ] Frame terakhir: nama produk + track + URL repo
- [ ] **4. Problem statement 1 kalimat** — menyebut untuk siapa dan masalah apa
- [ ] **5. Track = AI Agents & Assistants** + daftar lengkap nama anggota
- [ ] **6. Post sosmed** publik, men-tag akun resmi Sectors — **link post disalin ke form**

## 6. Menit terakhir

- [ ] Buka setiap link dari **browser incognito dan HP** — bukan dari laptop yang sudah login
- [ ] Deploy Vercel hidup dan tidak error
- [ ] Screenshot form submission yang sudah terisi, sebelum menekan submit
- [ ] Submit
- [ ] 🔒 **Umumkan ke tim: repo dikunci. Jangan ada yang push apa pun.**

### Satu-satunya pengecualian freeze
Credential bocor. Prosedur: lapor di Slack `#support` → cabut & rotasi key **lebih dulu** → baru push satu commit yang isinya **hanya** penghapusan credential tersebut.
