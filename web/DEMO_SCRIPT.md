# Daftar Rekam — N6 (ticker yang bercerita)

Dipilih dari data asli 43 investigasi (s/d 30 Sep). Urutan ini sengaja: mulai
dari "agen tahu kapan berhenti", naik ke investigasi penuh, lalu dua layar
agentik puncak. Keempat momen agentik (perutean adaptif, penghentian dini,
eskalasi, memori) semuanya tampil, dengan keyakinan yang kredibel — bukan skor
tinggi dari satu komponen.

Semua rute statis. Ganti `localhost:3000` dengan URL Vercel saat rekaman.

---

## 1 · TRUK-2026-09-09 — "Agen tahu kapan berhenti"
`/investigasi/TRUK-2026-09-09/`

- NORMAL · skor 20 · keyakinan 40% · **0 kredit** · 2 langkah
- Dua probe termurah (volume_anomaly, free_float) keduanya **refuted** → agen
  berhenti dini, tak menghabiskan jatah. Hemat ~100% vs investigasi menyeluruh.
- **Jujur:** narasi jatuh ke template (planner LLM gagal lolos skema) — tampil
  apa adanya, bukan disembunyikan.
- Momen: **penghentian dini**.
- Narasi: *"Agen tidak menginvestigasi semua hal. Dua pemeriksaan termurah sudah
  cukup membantahnya, lalu ia berhenti — nol kredit."*

## 2 · NICK-2026-09-18 — "Investigasi penuh, keyakinan tertinggi"
`/investigasi/NICK-2026-09-18/`

- WATCH (waspada) · skor 64 · **keyakinan 92%** (tertinggi) · 5 langkah · cakupan 5/6
- Holding kecil (~Rp1,56T) yang naik +103% dalam 119 hari bursa → agen menyusuri
  lima komponen, dua terkonfirmasi (broker_concentration, price_fundamental).
- Momen: investigasi menyeluruh, berhenti saat bukti cukup. Tanpa gimmick —
  memperlihatkan agen yang teliti, bukan cuma pintar berhemat.
- Narasi: *"Saat memang perlu, agen menggali dalam: lima langkah, keyakinan 92%,
  tiap angka tertelusuri ke buktinya."*

## 3 · ASLI-2026-09-22 — "Agen beradaptasi, dengan narasi LLM asli" ★
`/investigasi/ASLI-2026-09-22/`

- WATCH (waspada) · skor 62 · keyakinan 73% · 0 kredit · cakupan 4/6
- **Keempat momen dalam satu layar**, dan narasinya **LLM asli** (bukan template):
  - **perutean adaptif** (L4 structural, di luar rencana awal)
  - **eskalasi** (L3: +3 kredit dengan alasan tertulis soal free float 37%)
  - **memori** (mengingat ASLI-2026-09-18 saat menyusun rencana)
  - **penghentian dini** (4 langkah)
- Layar agentik utama. Buka blok "Momen kunci agen" + klik satu sitasi bukti.
- Narasi: *"Ini yang membedakan agen dari if-else: ia keluar dari rencananya,
  minta tambah jatah dengan alasan, mengingat investigasi sebelumnya — lalu
  menjelaskannya sendiri."*

## 4 · JAWA-2026-09-30 — "Investigasi ulang: memori mengubah rencana" ★
`/investigasi/JAWA-2026-09-30/` · lalu `/riwayat` (filter JAWA)

- WATCH (waspada) · skor 73 · **keyakinan 88%** · cakupan 5/6 · eskalasi + adaptif
- Rencananya eksplisit berbasis memori: *"Fokus pada APA YANG BERUBAH sejak
  29-09…"* — agen tak mengulang dari nol, ia melanjutkan dari kunjungan kemarin
  (memory_ref → JAWA-2026-09-29, skor 71 → 73).
- Tutup dengan **/riwayat** difilter ke JAWA: tren skor banyak kunjungan dalam
  satu grafik, memperlihatkan agen yang kembali tiap hari dan menyesuaikan.
- Momen: **memori + eskalasi + perutean adaptif + penghentian dini**.
- Narasi: *"Keesokan harinya agen datang lagi, ingat temuan kemarin, dan hanya
  memeriksa yang berubah. Riwayat ini yang membuatnya terasa seperti analis,
  bukan laporan sekali jalan."*

---

### Catatan kurasi
- **Hindari sebagai hero:** run berskor 100 (ASLI-09-11, NICK-09-17) — itu 100
  dari **1/6 komponen**, keyakinan ~22%. UI sudah menandainya tipis; jangan
  jadikan sorotan karena terbaca seperti kepastian, padahal bukan.
- Cadangan eskalasi lain bila perlu variasi: JAWA-2026-09-14 (skor 81).
- Disclaimer permanen ada di tiap halaman — biarkan terlihat di frame.
