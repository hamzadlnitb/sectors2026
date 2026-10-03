# Naskah Video Penjurian — PANTAU

Video penjurian, **maks 3:00**. Struktur mengikuti template `RESEARCH.md` §5 dan
syarat `TASK.md` B3. Semua layar memakai data asli (49 investigasi, s/d 2 Okt 2026).

**Problem statement (1 kalimat, untuk submission):**
PANTAU membantu investor ritel IDX memahami apa yang menggerakkan saham yang
bergerak tidak wajar, lewat agen AI yang menyelidiki data Sectors dan menunjukkan
bukti untuk setiap temuannya.

**Persona:** Rina, 26 tahun, investor ritel. (Persona cerita, bukan pengguna asli.
Kutipan pengguna asli ada di beat 2:30.)

---

## Prasyarat sebelum merekam

1. **Rekam dari build statis lokal**, bukan `npm run dev`. Mode dev menampilkan
   tombol bulat "N" (indikator Next.js) di pojok kiri bawah yang ikut terekam.
   Dari folder `web/`:

   ```bash
   npm run build
   python -m http.server 3000 --directory out
   ```

   Lalu buka `http://localhost:3000`. Web tidak di-deploy; yang tampil sama persis
   dengan yang juri dapat saat menjalankan repo.
2. **≥3 pengguna Indonesia asli** mencoba PANTAU, dengan kutipan verbatim + izin tertulis.
3. **Uji jalur `selidiki` end-to-end:** buka issue nyata, tunggu run berikutnya,
   pastikan bot menyelidiki dan menutup issue dengan tautan hasil. Kalau belum
   terbukti, **lewati beat 1:52** dan bagi waktunya ke beat ASLI dan JAWA.
4. Data terbaru sudah diekspor dan `npm run build` hijau.
5. Browser bersih: tema gelap, zoom 110–125% supaya teks terbaca, tab lain
   ditutup, bookmark bar disembunyikan, hard refresh sebelum tiap take. Pakai
   layar penuh (F11) supaya address bar `localhost` tidak mengganggu frame.

## Layar yang dipakai

| Beat | URL / layar |
| --- | --- |
| Otomatis | `/`, `/papan`, GitHub `.github/workflows/daily.yml`, daftar commit `pantau-bot` |
| Penghentian dini | `/investigasi/PACK-2026-09-29/` |
| Momen "aha" | `/investigasi/ASLI-2026-09-22/` |
| Memori | `/investigasi/JAWA-2026-09-30/`, lalu `/riwayat` (filter JAWA) |
| Permintaan | `/` → search `BBRI` → issue `selidiki: BBRI` |
| Sectors + validasi | diagram arsitektur, `/metodologi` |

---

## Naskah

### 0:00–0:12 · Masalah dan audiens

- **Layar:** mockup chat grup investor: *"JAWA volumenya meledak hari ini, ada apa ya?"*
- **Narasi:** "Ini Rina, 26 tahun, investor ritel. Setiap hari grupnya ramai
  membahas satu kode saham: volumenya meledak, harganya naik. Pertanyaannya selalu
  sama: siapa yang sebenarnya menggerakkan saham ini?"
- **Teks di layar:** *Investor ritel IDX · satu pertanyaan yang jarang terjawab*

### 0:12–0:24 · Kenapa belum terpecahkan

- **Layar:** enam tab browser berjejer: broker summary, volume, laporan keuangan,
  free float, aliran asing, pengumuman bursa.
- **Narasi:** "Untuk menjawabnya, Rina harus membuka enam sumber data,
  membandingkannya satu per satu, lalu menyimpulkan sendiri. Butuh berjam-jam."
- **Teks di layar:** *6 sumber · manual · rawan salah baca*

### 0:24–0:44 · PANTAU bekerja sendiri

- **Layar:**
  1. landing: hero + panel sorotan "update 2 Okt"
  2. Papan Waspada: pilih tanggal, kandidat dengan tanda "diselidiki"
  3. GitHub: `daily.yml`, sorot baris `cron: "30 10 * * 1-5"`
  4. daftar commit `pantau-bot`: *"chore(runs): sapuan Tier-1 + 3 investigasi … [otomatis]"*
- **Narasi:** "PANTAU adalah agen investigasi saham IDX. Setiap hari bursa, terjadwal
  pukul 17.30 WIB, ia menyapu pasar lewat Sectors API, memilih kandidat yang
  bergerak tidak wajar, lalu menyelidikinya sendiri, tanpa ditunggui. Setiap run
  tercatat sebagai commit otomatis di GitHub."
- **Teks di layar:** *Terjadwal · tanpa campur tangan · tercatat di GitHub*

### 0:44–0:58 · Agen tahu kapan berhenti

- **Layar:** `/investigasi/PACK-2026-09-29/`:
  1. sorot rencana: *"Yang berubah sejak 24-09: harga +15% dalam 5 hari…"*
  2. putar ulang sampai langkah 4
  3. kartu "Berhenti dini" + keyakinan 80%
- **Narasi:** "PACK naik 15 persen dalam lima hari. Agen menyusun dugaan, mengujinya
  satu per satu, dan begitu semua dugaan utama gugur, ia berhenti di langkah
  keempat dari enam. Hasilnya NORMAL, dengan keyakinan 80 persen."
- **Teks di layar:** *Penghentian dini · langkah 4 dari 6 · NORMAL*

### 0:58–1:35 · Momen "aha": agen berpikir ⭐

- **Layar:** `/investigasi/ASLI-2026-09-22/`:
  1. rencana investigasi
  2. putar ulang penalaran langkah demi langkah
  3. sorot langkah 3: eskalasi +3 kredit dengan alasan tertulis
  4. sorot langkah 4: perutean adaptif (probe di luar rencana)
  5. narasi berlabel LLM, klik satu angka → buku bukti terbuka (endpoint + `as_of` + kredit)
  6. panel "Tanya agen" (±6 detik): klik chip *"Apa momen agentiknya?"* → jawaban
     menyebut keempat momen → klik *"Lihat momen →"*, halaman menggulir ke kartu momen
- **Narasi:** "Di ASLI, kita bisa melihat agen berpikir. Ia menyusun rencana, lalu
  mengubahnya di tengah jalan. Di langkah tiga, ia meminta tambahan tiga kredit
  dengan alasan tertulis: free float hanya 37 persen. Di langkah empat, ia membuka
  pemeriksaan yang tidak ada di rencana awal. Narasinya ditulis LLM, dan setiap
  angka bisa diklik sampai ke endpoint Sectors dan tanggal datanya. Tidak ada angka
  tanpa bukti. Mau penjelasan cepat? Tanya agennya. Jawabannya ditarik dari
  rekaman investigasi ini, bukan dikarang, dan langsung menunjuk ke bagian yang
  dimaksud."
- **Teks di layar:** *Eskalasi · Perutean adaptif · Tiap angka tertelusuri · Tanya agen*

### 1:35–1:52 · Investigasi ulang: yang dilihat adalah perubahan

- **Layar:**
  1. `/investigasi/JAWA-2026-09-30/`, sorot rencana *"Fokus pada APA YANG BERUBAH sejak 29-09"*
  2. `/riwayat` dengan filter JAWA (grafik tren skor)
  3. potongan 2 detik halaman yang sama dalam tampilan lebar HP (mode responsif
     DevTools, atau HP yang membuka laptop lewat jaringan Wi-Fi yang sama)
- **Narasi:** "Keesokan harinya agen kembali ke JAWA. Ia tidak mengulang dari nol,
  ia hanya memeriksa apa yang berubah sejak kemarin. Hasilnya ALERT dengan keyakinan
  88 persen. Di halaman Riwayat, perjalanan skor JAWA terlihat dari hari ke hari,
  dan tampilannya tetap rapi di layar HP."
- **Teks di layar:** *Fokus pada perubahan · keyakinan 88%*

### 1:52–2:05 · Siapa pun bisa meminta investigasi (bersyarat, lihat prasyarat 3)

- **Layar:** landing → ketik `BBRI` di search → muncul *"BBRI belum pernah
  diselidiki. Minta agen menyelidiki →"* → form issue `selidiki: BBRI` → issue
  yang sudah ditutup bot dengan tautan hasilnya.
- **Narasi:** "Saham yang belum diselidiki? Ketik kodenya dan kirim permintaan.
  Agen menyelidikinya di run berikutnya, lalu menautkan hasilnya."
- **Teks di layar:** *Permintaan → diselidiki di run berikutnya*

### 2:05–2:30 · Cara kerja dan kenapa Sectors jadi penopang

- **Layar:** diagram arsitektur (Sectors REST API → sapuan Tier-1 → agen dengan
  6 probe → skor deterministik → narasi tervalidasi sitasi → web), lalu
  `/metodologi`: bagian "Dua angka validasi" dan "Batasan yang diakui terbuka".
- **Narasi:** "Enam pemeriksaan agen mengambil data dari Sectors, termasuk data
  bandarmology seperti broker summary dan aliran asing yang jarang tersedia di
  tempat lain. Skor dihitung oleh kode, bukan oleh LLM. Angka pertama: precision
  at 20 sebesar 0,45, dengan median lima hari sebelum suspensi. Angka itu masih
  sementara karena sampelnya kecil. Angka kedua: apakah agen lebih hemat dari
  urutan pemeriksaan tetap? Pada 16 emiten uji, belum terbukti, dan itu kami
  tuliskan terbuka."
- **Teks di layar:** *Sectors REST API · skor deterministik · validasi apa adanya*

### 2:30–2:47 · Bukti dipakai orang

- **Layar:** **[ISI: rekaman atau kutipan pengguna asli + izin tertulis]**
- **Narasi:** **[ISI: kutipan verbatim pengguna. Jangan dikarang.]**
- **Teks di layar:** *nama atau inisial pengguna*

### 2:47–3:00 · Penutup

- **Layar:** landing, lalu frame akhir.
- **Narasi:** "PANTAU: agen investigasi untuk investor ritel yang ingin tahu cerita
  di balik pergerakan saham. PANTAU adalah alat informasi dan analisis, bukan
  saran investasi."
- **Frame akhir:** *PANTAU · Sectors Hackathon 2026 · Track 01 AI Agents &
  Assistants · github.com/hamzadlnitb/sectors2026* + disclaimer.

---

## Catatan kurasi

- **Kenapa PACK-09-29, bukan TRUK-09-09, untuk penghentian dini:** rencana TRUK-09-09
  memakai rencana cadangan, dan di layar tertulis "perencana LLM tidak menghasilkan
  keluaran yang lolos skema". PACK-09-29 rencana dan narasinya dari LLM, keyakinan
  80%, dan berhenti karena semua dugaan utama gugur.
- **Jangan jadikan sorotan** run berskor 100 (ASLI-09-11, NICK-09-17). Skor itu dari
  1/6 komponen dengan keyakinan ~22%, terbaca seperti kepastian padahal bukan.
- **Chat "Tanya agen" hanya sisipan ±6 detik di beat ASLI**, dibingkai sebagai
  penjelas rekaman, bukan chatbot bebas. "Chatbot ngobrol sama saham" ada di daftar
  JANGAN DIBANGUN (`RESEARCH.md` §3), jadi jangan dijadikan beat sendiri. Jawabannya
  deterministik dari transkrip (nol LLM saat dibuka) dan selalu menunjuk ke bagian
  halaman atau bukti.
- **Pakai chip "Apa momen agentiknya?", bukan "Bukti apa yang paling menentukan?".**
  Di ASLI-09-22 semua bukti tercatat 0 kredit (data dari cache warehouse), jadi
  jawaban "bukti termahal" akan menyebut "(0 kredit)" dan memilih bukti secara acak
  dari yang nilainya seri.
- **Memori tidak disebut di beat ASLI** supaya beat itu tidak terlalu padat; memori
  sudah jadi inti beat JAWA.
- **Buku bukti hanya dibuka di ASLI-09-22.** Di semua investigasi, tiap baris bukti
  tertulis "0 credits" (biaya dicatat per probe, bukan per bukti). Di ASLI-09-22
  total kreditnya memang 0, jadi konsisten. Di PACK-09-29 dan JAWA-09-30 (total
  4 dan 5 kredit), jangan menggulir sampai buku bukti; cukup berhenti di replay.
- **Cadangan bila butuh pengganti:** NICK-2026-09-18 (investigasi penuh, 5 langkah,
  keyakinan 92%).
- **Jangan klaim:** "live" (web memutar ulang hasil run otomatis), agen lebih hemat
  dari baseline (klaim ini sudah dicabut di Metodologi), atau pemakaian MCP (kita
  memakai REST API, dan itu sah menurut rubrik).
- **Soal jam:** cron dijadwalkan 10:30 UTC (17:30 WIB), tapi run aktual tercatat
  sekitar 16:20–17:10 UTC karena antrean scheduler GitHub. Narasi memakai kata
  "terjadwal". Jangan zoom ke jam commit sambil menyebut 17.30.
- **Kandidat skor teratas kadang tidak diselidiki** (mis. JAWA 1–2 Okt): itu cooldown
  anti-redundansi yang disengaja di `tools/investigate_watchlist.py`, bukan bug.
  Kalau juri bertanya lewat repo, jawabannya ada di sana.

## Catatan produksi

- Narasi ±350 kata (±2:30 waktu bicara pada tempo normal), ditambah kutipan
  pengguna ±15 detik. Sisa ruangnya untuk jeda dan transisi layar. Ukur saat
  gladi; kalau lewat 3:00, potong beat 1:52 dulu.
- Rekam 3–4 take, ambil yang terbaik. Jangan percepat audio.
- Beri subtitle. Disclaimer harus terlihat di layar.
- Unggah ≥24 jam sebelum deadline, lalu cek link dari jendela incognito.
