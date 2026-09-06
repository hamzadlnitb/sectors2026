# RESEARCH.md — Basis Keputusan

Dokumen ini merekam hasil riset lomba + riset pemenang hackathon internasional sejenis.
Semua keputusan di `ARCHITECTURE.md` mengacu ke sini.

---

## 1. Profil Lomba

**Sectors Hackathon 2026** — Supertype × Sectors × Algoritma. Online, Indonesia-wide.
Situs: https://hackathon.sectors.app · Rules: https://hackathon.sectors.app/rules

| Milestone | Tanggal |
| --- | --- |
| Build period dibuka | 19 Agustus 2026 |
| **Registrasi tutup** | **22 September 2026, 23:59 WIB** |
| **Submission tutup** | **30 September 2026, 23:59 WIB** |
| Judging (asinkron) | 1–8 Oktober 2026 |
| Pengumuman | 9 Oktober 2026 |

- Tim 1–4 orang. 1 proyek per tim. Roster terkunci saat klaim kredit.
- Hadiah: IDR 50.000.000 (30 jt cash + 20 jt kredit API).
- Jatah data: **1.000 kredit API Sectors** per tim.

### Bobot penilaian (ini yang menyetir semua keputusan)

| Kriteria | Bobot | Yang dinilai |
| --- | --- | --- |
| **Real-world usability** | **40%** | Bisa dipakai orang beneran hari ini dan memberi manfaat? |
| **Video demo & storytelling** | **30%** | Seru, engaging, well-produced; problem tersampaikan ke audiens yang dituju |
| **Technical depth & execution** | **30%** | **Diverifikasi dari repo GitHub.** Seberapa inovatif pemakaian Sectors API/MCP; nyata, fungsional, well-engineered, **bukan dipalsukan untuk demo** |

Kutipan resmi panitia: *"We don't judge how sophisticated your code is. We judge whether what you build can genuinely be used by real people, today, with Sectors data at its core."*

**Konsekuensi:** 70% nilai ada di framing masalah + video. Juri = tim internal Sectors/Supertype (praktisi data IDX) yang akan langsung mencium pemakaian API yang dangkal. **Tidak ada pitch live** — repo dan video harus berbicara sendiri.

### Gerbang eligibility (pass/fail, sebelum scoring)
- Submission lengkap; produk **jalan**; data Sectors jadi sumber inti ("produk harus kehilangan fungsi intinya kalau data Sectors dicabut"); onboarding semua anggota terverifikasi.

### Aturan keras
- Repo **wajib dibuat di dalam build period** (≥19 Agu 2026). Commit history boleh diperiksa.
- **Freeze total saat submit** — tidak ada bug fix setelahnya. Pengecualian hanya untuk mencabut credential yang bocor.
- Proyek eksklusif untuk lomba ini; tidak boleh reuse proyek lama; tidak boleh disubmit ke lomba lain.
- **Dilarang eksekusi order jual/beli otomatis** di semua track.
- **Dilarang memberi saran finansial.** Wajib posisikan sebagai alat informasi/analisis + disclaimer.
- AI coding tools bebas dipakai, tanpa kewajiban disclose.

### Deliverable submission
1. Link repo publik (tetap publik ≥90 hari, tanpa API key)
2. **Teaser 1 menit** — screen recording produk berjalan, publik di YouTube/sosmed
3. **Judging video maks 3 menit** — problem, audiens, core workflow end-to-end
4. Problem statement 1 kalimat
5. Pilihan track + daftar anggota
6. Post sosmed men-tag akun resmi Sectors

### Track & syarat lolosnya

| Track | Syarat wajib | Diskualifikasi eksplisit |
| --- | --- | --- |
| **T1 AI Agents & Assistants** | Ada agent logic / orkestrasi buatan sendiri. LLM wajib. | Cuma nyambungin klien AI jadi (Claude/OpenClaw/Hermes) ke Sectors MCP + prompt. "Kalau produknya hilang begitu prompt kalian dicabut dari klien orang lain, tidak lolos." |
| **T2 Automation & Workflows** | Jalan otonom by schedule/trigger tanpa campur tangan per siklus. LLM opsional. | Workflow yang harus dijalankan manual tiap kali. **Video wajib menampilkan konfigurasi schedule + log/timestamp/screenshot unattended run.** |
| **T3 Market Intelligence** | Menghasilkan **derived insight** — analisis, bukan datanya. LLM opsional. | Produk yang hanya menampilkan data mentah dalam bentuk visual lain, "however well presented". |

---

## 2. Inventaris Data Sectors (peluang diferensiasi)

MCP: `https://sectors-mcp.supertype.ai/mcp` (Streamable HTTP, header `Authorization: Bearer <key>`), 65+ tools.
REST: `https://api.sectors.app/v2/...`, header `Authorization: <key>`. Tiap endpoint v2 punya biaya **1 / 2 / 3 kredit**.

**Data komoditas (semua orang punya, nilai inovasi ≈ 0):** harga, market cap, PE/PBV, dividen, laporan kuartalan, index harian.

**Data langka milik Sectors (ini moat kita):**
- `fetch-broker-summary`, `fetch-broker-summary-top`, `fetch-broker-activity-top`, `fetch-top-brokers`, `fetch-brokers` — **bandarmology**, tidak ada di Yahoo/TradingView
- `fetch-foreign-flow` — net arus broker asing harian per saham
- `fetch-filings` — insider trading buy/sell IDX
- `fetch-shareholders-composition` — komposisi pemegang saham bulanan (lokal vs asing)
- `fetch-suspensions` — riwayat suspensi + alasan resmi ← **sumber label untuk kalibrasi**
- `fetch-free-float`, `fetch-company-segments`, `fetch-corporate-actions`
- Vertikal **mining Indonesia** (izin IUP, lelang izin, situs, produksi, cadangan, ekspor, ownership tree)
- Lintas bursa: IDX + SGX (buyback, short sell) + KLSE

**Endpoint murah cakupan-pasar (kunci hemat kredit):**
- `fetch-close` — harga tutup **seluruh ticker IDX** dalam 1 panggilan per tanggal
- `fetch-most-traded-stocks`, `fetch-companies-top-changes`, `fetch-suspensions`, `fetch-filings`, `fetch-free-float` — semuanya bisa dipanggil market-wide/rentang tanggal

---

## 3. Temuan Riset Pemenang (yang bisa kita terapkan)

Ringkasan taktik berbukti, diurutkan dari yang paling berpengaruh untuk rubrik lomba ini.

1. **Satu persona, satu workflow.** Proyek menang menunjukkan satu kemampuan dengan sangat baik, bukan lima setengah jadi. "Feature stuffing" (8–10 fitur yang tidak nyambung) adalah keluhan juri paling umum. → Problem statement 1 kalimat harus menyebut persona konkret sebelum baris kode pertama ditulis.
2. **Tulis skrip video 3 menit SEBELUM commit pertama.** Video = 30% nilai dan tidak ada pitch live untuk menyelamatkan. Skrip adalah spec; apa pun yang tidak masuk skrip = out of scope.
3. **Bangun di atas data proprietary, bukan deret harga.** Kriteria teknis bertanya harfiah "how innovative is the use of Sectors API". Data yang bisa direplikasi Yahoo Finance = nilai inovasi nol. Preseden: T. Rowe Price memenangkan "Data Innovator Award" di Bloomberg Code Crunch London justru karena pemakaian dataset berita yang tidak lazim.
4. **JANGAN bangun ulang apa pun yang sudah jadi recipe resmi Sectors.** Docs Sectors sudah memuat: n8n NL screener, multi-agent financial research, ReAct conversational agent, SectorScan Streamlit dashboard, portfolio optimization, Looker Studio dashboard, konektor OAuth ke Claude/ChatGPT. Menyerahkan ulang tutorial jurinya sendiri adalah langkah paling berisiko yang tersedia.
5. **Tunjukkan bukti unattended run: log + timestamp.** Klausul "not faked for the demo" berlaku di semua track, bukan cuma T2. Preseden: finalis trading agent AI Agent Olympics menyertakan *read-only audit trail untuk juri* + 366 trade out-of-sample + 11 hari log live.
6. **Kirim satu angka terukur, bukan vibe.** Pemenang Hack the North (Cua) menang lewat "systematic engineering rather than novel architecture". MaestrIA (Anthropic Built with Opus 4.7) dikreditkan karena knowledge base 17 aturan diagnostik yang menaikkan akurasi **74% → 81%**. Satu angka validasi dengan eval set di repo > tiga fitur tambahan.
7. **Repo adalah bagian dari pitch** — dinilai eksplisit. Kegagalan yang diburu juri: "video mengesankan tapi kodenya minim". → README + diagram arsitektur + tabel endpoint yang dipakai & alasannya + one-command run + seeded demo data + tes + commit history yang wajar.
8. **Satu orang khusus pegang UI + video sejak hari pertama.** Pemenang Grand Prize Cal Hacks 12.0 (FaceTimeOS) mendedikasikan satu anggota penuh untuk UI karena "itu yang dilihat semua juri".
9. **Rekayasa jalur demo supaya mustahil gagal — buang fitur yang goyah.** FaceTimeOS menghapus fitur klik dari demo karena agennya sering meleset. Tanpa Q&A live, satu stall di rekaman tidak bisa diselamatkan.
10. **Buka video dengan masalah, bukan teknologi.** Sebut audiens dengan lantang di 15 detik pertama.
11. **Orkestrasi nyata, bukan prompt (khusus T1).** ARIA menang "Best Use of Claude Managed Agents" dengan lima agen terkoordinasi dan **satu hari penuh khusus perencanaan arsitektur sebelum coding**.
12. **Layer sitasi/provenance = kredibilitas termurah di finance AI.** *Cite-Before-Act MCP* memenangkan **Best Overall** di MCP 1st Birthday Hackathon (Anthropic/Gradio) — middleware keselamatan mengalahkan semua aplikasi di atasnya. Sekaligus memenuhi larangan "no financial advice".
13. **Selesaikan masalah yang jurinya sendiri rasakan.** IDX menembus **30,27 juta SID** per 7 Agu 2026 (+48,78% YTD), **99,80% ritel**, **54,12% di bawah 30 tahun**; ritel = 51,1% nilai transaksi Juli 2026 vs 35,8% asing institusi. OJK & IDX sedang mengevaluasi rezim **Papan Pemantauan Khusus / Full Call Auction** setelah keluhan Komisi XI DPR soal transparansi dan spekulasi. Finalis BI-OJK Hackathon 2025 mengelompok di anti-scam, deteksi fraud, dan perlindungan konsumen → framing **investor protection** sangat laku di panel juri finansial Indonesia.
14. **Lokalkan habis-habisan.** Output Bahasa Indonesia, format IDR, kalender & sesi bursa WIB, konsep khas IDX (papan pemantauan khusus, ARA/ARB, free float, rights issue, saham gorengan), dan kosakata **bandarmology** yang benar-benar dipakai trader ritel.
15. **Submit lebih awal; anggap freeze itu nyata.** Banyak submission mati di gerbang eligibility karena kelengkapan, bukan kualitas.

### Arketipe yang berulang menang di hackathon finance+AI
- **Indikator komposit stres/divergensi** — CADI (Cross-Asset Divergence Indicator) menang Bloomberg Code Crunch Singapura perdana.
- **Sinyal dari dataset alternatif yang tak tersentuh** — Grand Prize Bloomberg Kyushu 2025 lewat dataset sentimen berita.
- **Meja riset multi-agen dengan deliverable nyata** — Portfolio Intelligence Platform (Best Consumer, MCP Birthday); Apollo Deep Research Meta Agent; ARIA.
- **Brief harian / bot alert tanpa pengawasan** — hanya menang kalau konfigurasi scheduler + log berjalan ditampilkan.
- **Detektor anomali / manipulasi** — Qdrant 2025 memberi hadiah untuk sistem deteksi & safety, bukan RAG biasa; finalis BI-OJK 2025 padat deteksi fraud.
- **Layer governance/trust** — Cite-Before-Act (Best Overall).
- **Mesin skoring yang mengenkode keahlian domain** — MaestrIA (17 aturan diagnostik terenkode); Medkit menang 1st place sebagian karena **tiga fakultas kedokteran mulai pilot** selama masa penjurian.

### Daftar JANGAN DIBANGUN (jenuh / berisiko kena aturan)
1. Chatbot "ngobrol sama saham IDX" — GPT wrapper, recipe-nya sudah ada.
2. Sectors MCP + system prompt di Claude/ChatGPT — didiskualifikasi eksplisit di halaman T1.
3. Dashboard Streamlit/Looker IDX — recipe resmi sudah ada, dan gagal tes T3.
4. n8n natural-language screener — recipe resmi sudah ada.
5. "Financial research crew" multi-agen generik — recipe resmi sudah ada.
6. Bot auto-trading / apa pun yang terhubung eksekusi broker — dilarang.
7. Robo-advisor / "sebaiknya beli X?" — melanggar larangan saran finansial.
8. Prediksi harga LSTM dari OHLC — nilai inovasi API nol, tidak terfalsifikasi dalam 3 menit.
9. Portfolio optimizer Markowitz — recipe resmi sudah ada.
10. RAG laporan tahunan tanpa output turunan.
11. Crypto/DeFi — di luar brief.
12. Landing page + waitlist + "visi" Figma — gagal gerbang "produk jalan".

---

## 4. Checklist Penilaian Mandiri

Dinilai jujur tiap Minggu malam. Kolom skor di `TASK.md` §Papan Skor Mandiri.

### Gerbang (pass/fail — cek mingguan, jangan di akhir)
- [ ] Core workflow jalan end-to-end hari ini, di mesin bersih, dari repo publik
- [ ] Mencabut data Sectors mematikan produk (tulis satu kalimat pembuktiannya)
- [ ] Semua anggota onboarded di sectors.app; kredit diklaim; roster terkunci
- [ ] Repo publik, commit pertama ≥19 Agu 2026, **nol API key di riwayat git**
- [ ] Syarat track terpenuhi harfiah (T1: orkestrasi agen buatan sendiri — produk tetap utuh
      kalau prompt kita dicabut dari klien AI orang lain)
- [ ] Nol kode eksekusi order; disclaimer terlihat di produk
- [ ] Kedua video terbuka dari incognito; post sosmed hidup dan men-tag Sectors

### Real-world usability — 40%
- [ ] Satu persona bernama, satu kalimat, tanpa "dan juga"
- [ ] ≥3 pengguna Indonesia asli mencoba sebelum submit (nama/kutipan masuk video)
- [ ] Output Bahasa Indonesia, format IDR, kalender & jam WIB benar
- [ ] Orang lain bisa memakainya besok tanpa bantuan setup — URL ter-deploy atau one-command run
- [ ] Masalahnya benar-benar dialami pelaku pasar IDX, bukan "investor butuh insight" yang generik

### Video & storytelling — 30%
- [ ] Masalah dinyatakan dan audiens disebut di 15 detik pertama
- [ ] Screen recording produk **asli**, bukan slide
- [ ] Setiap detik terskrip; rehearsal terukur di bawah 3:00
- [ ] Audio bersih, font terbaca, nol dead air, nol "biasanya sih jalan"
- [ ] Ada satu momen "oh, ternyata bisa begitu"
- [ ] Teaser 1 menit adalah potongan terpisah yang lebih padat, tanpa talking head

### Technical depth & execution — 30%
- [ ] ≥4 keluarga endpoint Sectors digabung jadi sesuatu yang tak disediakan satu pun di antaranya
- [ ] Minimal satu endpoint yang tim lain tidak akan terpikir memakainya (broker flow / foreign flow / mining / segments / free float / SGX-KLSE)
- [ ] README: diagram arsitektur + tabel pemakaian endpoint + alasan tiap panggilan
- [ ] Eval set / backtest / hasil validasi ter-commit, dengan angka
- [ ] Log berjalan, output bertanggal, atau screenshot yang membuktikan operasi tanpa pengawasan
- [ ] Caching, penanganan rate limit, jalur error — rekayasa yang terlihat, bukan notebook
- [ ] Riwayat commit terbaca seperti kerja bertahap yang nyata

---

## 5. Template Video

### Judging video — batas keras 3:00

| Waktu | Beat | Catatan |
| --- | --- | --- |
| 0:00–0:15 | **Masalah + siapa yang mengalaminya.** Konkret, Indonesia, spesifik. *"Setiap pagi, Rina buka grup Telegram dan lihat satu kode saham…"* | Sebut audiens dengan lantang. Buat juri ikut merasakan frustrasinya |
| 0:15–0:30 | **Kenapa hari ini belum terpecahkan.** Satu screenshot status quo yang menyakitkan (6 tab browser, broker summary mentah) | Menyiapkan kontras |
| 0:30–2:00 | **Screen recording core workflow end-to-end.** Data nyata, panggilan Sectors nyata. Momen "aha" di sekitar 1:15. Tampilkan konfigurasi cron + log unattended run ber-timestamp | Potong apa pun yang bisa tersendat |
| 2:00–2:25 | **Cara kerjanya + kenapa Sectors jadi penopang.** Diagram arsitektur 15 detik; sebut endpoint spesifik; sebut angka validasi ("presisi X%, median peringatan Y hari lebih awal, eval set ada di repo") | Langsung menyuapi kriteria teknis yang diverifikasi dari repo |
| 2:25–2:45 | **Bukti dipakai orang.** Investor ritel asli, kutipan, reaksi, atau artefak yang dihasilkan | Bukti terkuat untuk bobot 40% |
| 2:45–3:00 | **Penutup: untuk siapa, apa selanjutnya, disclaimer di layar.** Frame terakhir: nama + track + URL repo | Kepatuhan + daya ingat |

### Teaser — 60 detik, publik

| Waktu | Beat |
| --- | --- |
| 0:00–0:05 | Hook — satu baris teks di layar menyatakan hasilnya, bukan kategorinya |
| 0:05–0:45 | Footage produk tanpa jeda, potongan cepat, **caption bukan narasi** (harus jalan tanpa suara di sosmed) |
| 0:45–0:55 | Frame hasil — artefak yang dihasilkan atau angka yang bergerak |
| 0:55–1:00 | Nama produk, tag Sectors Hackathon 2026, link repo |

### Catatan produksi
- Rekam 3–4 take, ambil yang terbaik. Jangan percepat audio agar muat.
- Pra-isi semua data dan cache respons API supaya tidak ada loading lambat di kamera.
- Unggah ≥24 jam sebelum deadline; verifikasi kedua link dari kondisi logged out.
- Bahasa Indonesia tidak dipenalti dan akan terbaca lebih otentik di panel juri ini — tapi tetap beri subtitle.

---

## 6. Bacaan Strategis

Rubriknya 40% "bisa dipakai hari ini" + 30% storytelling melawan hanya 30% teknis, dinilai asinkron oleh tim vendor API sendiri, dari sebuah video dan sebuah repo.

Kombinasi itu berarti: **alat sederhana yang benar-benar dipakai orang, dibangun di atas data Indonesia milik Sectors sendiri (broker flow, foreign flow, mining, segments, lintas bursa), dengan satu angka validasi terukur di repo dan cerita 3 menit yang rapat berisi pengguna ritel Indonesia asli — mengalahkan agen yang secara teknis ambisius tapi hanya pernah dijalankan oleh timnya sendiri.**
