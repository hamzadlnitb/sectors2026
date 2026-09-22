# AGENT_NADHILLA.md — Catatan Keterbatasan Web PANTAU

> Catatan dari lajur Web (Nadhilla) untuk dipelajari & diperbaiki bersama Hamzah & Melco.
> Tujuannya jujur: memetakan apa yang **belum ideal** supaya bisa diprioritaskan sebelum submit.
> Status data saat ditulis: 6 transkrip investigasi (5 ticker), tanggal 2026-09-09 & 2026-09-18.

---

## 1. Chatbot masih deterministik (dari transkrip JSON), belum pakai LLM

**Kondisi:** Jawaban chatbot ditarik dari `web/public/data/*.json` (langkah/bukti/momen) lewat pencocokan kata kunci — **bukan** LLM.

**Kenapa sengaja begitu:**
- **Aturan AD-1:** web dibangun sebagai situs **statis** (nol backend saat dibuka). Tak ada server untuk menyimpan API key dengan aman.
- **Keamanan:** memanggil LLM langsung dari browser = API key terekspos ke publik.
- **Anti-gagal saat penilaian asinkron (1–8 Okt):** chat deterministik tak bisa mati, nol biaya, dan **nol risiko halusinasi / kosakata saran finansial** (yang bisa berujung diskualifikasi).

**Dampak:** pengetahuan chatbot **terbatas pada isi transkrip** — tak bisa menjawab pertanyaan bebas di luar itu.

**Untuk jadi LLM sungguhan** perlu: backend/serverless (pegang key + panggil MiniMax + gerbang grounding + vocab-guard). Sudah dirancang di `docs/MIDDLEWARE_CONTRACT.md` (usulan **C6**), frontend sudah disiapkan *drop-in* (`sourceForMode('live')`). **Belum dibangun.**

---

## 2. Baru ada 6 investigasi (5 ticker), hanya dari 2 tanggal

**Kondisi:** `runs/investigations/` cuma berisi:
- **09-09:** JAWA, SCCO, TRUK
- **09-18:** ASLI, JAWA, NICK

**Kenapa:**
- **09-09** = run **contoh manual** saat Hamzah membangun agen (bukan hasil cron).
- **09-18** = hasil **cron Tahap-2** setelah `MINIMAX_API_KEY` dipasang.
- **Tanggal 10–17 Sep kosong** karena key belum ada saat itu; **21 Sep hangus** karena bug commit cron (sudah diperbaiki via PR #15).

**Dampak:** cerita demo tipis; banyak tanggal watchlist tanpa investigasi. **Lane: Hamzah/Melco (cron & agen).**

---

## 3. Papan Waspada: 15 kandidat/hari, hanya ~3 dianalisis

**Kondisi:** tiap tanggal sapuan Tier-1 menandai **15 kandidat**, tapi agen hanya menyelidiki **beberapa teratas** (hemat kredit). Sisanya berlabel **"belum diselidiki"** dan **tak bisa dibuka** (memang belum ada transkripnya).

**Dampak:** wajar & jujur, tapi mayoritas baris belum ada detailnya. Bisa diperbaiki dengan menaikkan `--top N` di cron atau backfill. **Lane: Hamzah/Melco.**

---

## 4. Yang diselidiki BUKAN "top-3 skor seleksi" — ada ketidakcocokan

**Fakta (skor seleksi vs yang benar-benar diselidiki):**

| Tanggal | Top skor seleksi | Yang diselidiki | Catatan |
|---|---|---|---|
| **09-09** | ASLI 0.82, NICK 0.77, JAWA 0.52 | **JAWA, SCCO, TRUK** | ASLI & NICK (tertinggi) **dilewati** — karena ini run contoh manual, bukan top-N |
| **09-18** | ASLI 0.72, NICK 0.67, PACK 0.53, JAWA 0.52 | **ASLI, NICK, JAWA** | PACK (#3) dilewati; JAWA (#4) masuk karena **investigasi ulang / memori** |

**Kesimpulan:** daftar yang diselidiki **tidak transparan mengikuti peringkat skor seleksi**. Perlu diperjelas/didokumentasikan logika seleksi agen (top-N + aturan memori). **Lane: Hamzah (logika agen).**

---

## 5. Tambahan dari sisi Web (temuan lain)

**a. Data tidak ter-update otomatis ke web.**
Web statis → transkrip baru dari cron **tak muncul** sampai seseorang menjalankan `to_json` + rebuild + commit. **Usul:** tambahkan langkah `to_json` di CI setelah cron commit (RENCANA 7C). **Lane: Melco.**

**b. Momen agentik yang tampil masih miskin.**
Data asli sekarang hanya punya **penghentian dini** + **1 memori** (JAWA-18). **Belum ada eskalasi & perutean adaptif** sama sekali → dua dari empat "momen agentik" Track-1 belum bisa didemokan dengan data nyata. **Lane: Hamzah.**

**c. Dua angka validasi di Metodologi masih sementara (provisional).**
Menunggu `reports/validation.md` final dari Hamzah. **Lane: Hamzah.**

**d. Chat LLM / mode live belum ada.**
Baru proposal (C6 + MIDDLEWARE_CONTRACT). Butuh sign-off bertiga + backend + freeze-timing.

**e. Mode terang ("paper") jadi sekunder.**
Default sekarang navy (gelap); mode terang tetap ada tapi kurang teruji.

**f. Belum ter-deploy publik (Vercel).**
Perlu deploy (Root Directory = `web`) untuk verifikasi dari HP/incognito. **Lane: Nadhilla.**

**g. UI & copywriting masih terasa "AI-generated" — butuh masukan.**
Tampilan dan teks web saat ini masih terasa **generik / seperti hasil generate AI** — kurang karakter, nada kurang manusiawi, dan berisiko terlihat seperti template. Karena ini **hackathon Sectors sendiri dan orisinalitas dinilai**, ini bukan hal sepele. Butuh **masukan bersama** (idealnya juga mata orang luar / desainer) untuk:
- **Copywriting**: nada bahasa yang lebih natural & khas, bukan kaku/generik; microcopy yang membumi untuk persona ritel (pegang HP di angkot, bukan Bloomberg terminal).
- **UI/visual**: identitas yang tidak seperti template, hierarki & detail yang lebih matang.
- **Konsistensi**: memastikan gaya (warna, tipografi, tone) terasa satu tangan & disengaja.

**Lane: Nadhilla (eksekusi), tapi butuh masukan bertiga + ide dari luar.**

---

## Ringkasan prioritas untuk dibahas bersama

| # | Isu | Pemilik | Prioritas |
|---|---|---|---|
| 2,3,4 | Investigasi sedikit & tak jelas top-N + banyak "belum diselidiki" | Hamzah/Melco | Tinggi (cerita demo) |
| 5a | Auto-export ke web di CI | Melco | Sedang |
| 5b | Eskalasi & adaptif belum ada di data nyata | Hamzah | Tinggi (Track-1) |
| 5c | Dua angka validasi final | Hamzah | Sedang |
| 1, 5d | Chatbot LLM (butuh backend + C6) | Bertiga | Opsional/stretch |
| 5f | Deploy Vercel | Nadhilla | Tinggi |
| 5g | UI & copywriting masih terasa AI-generated | Nadhilla + masukan tim | Sedang-tinggi (orisinalitas dinilai) |

> Catatan: **chat deterministik, situs statis, dan "belum diselidiki" itu keputusan sadar** (agar demo tak bisa gagal & tak berisiko diskualifikasi), bukan sekadar kekurangan. Yang benar-benar perlu diperbaiki: **kuantitas & kualitas investigasi (top-N, eskalasi/adaptif), auto-export, deploy, dan poles UI/copywriting.**
