# RENCANA_LIVE_AGENT.md — Live Chat & Arsitektur Agent↔Middleware↔Frontend

> **Status: PROPOSAL untuk diputuskan bertiga.** Belum ada kode yang diubah atas dasar dokumen ini.
> Sumber: hasil diskusi Ikhsan · Hamzah · Melco. Disusun oleh lajur Web (Nadhilla).

## 0. Tujuan & konteks

Empat catatan yang mau dikerjakan:

1. **Agent belum running automated** — dijalankan terjadwal tanpa ditunggui.
2. **Agent running background → middleware → frontend** — jejak agen mengalir ke UI.
3. **Live chat + function calling** — user bisa ngobrol dengan agen; agen memanggil tool saat itu juga.
4. **Log aktivitas agen di dashboard**.

Arah yang disepakati:

```
Agent  ⇄  Middleware  ⇄  Frontend      (agen jadi proses terpisah di backend)
```

## 1. Timeline resmi (dari RESEARCH.md / SUBMISSION.md) — JANGAN diabaikan

| Peristiwa | Tanggal |
| --- | --- |
| Registrasi tutup | 22 Sep 2026 |
| **Feature freeze internal** | **25 Sep 2026** |
| **Submit** | **29–30 Sep 2026, 23:59 WIB** |
| **Judging (ASINKRON)** | **1–8 Oktober 2026** |
| Pengumuman | 9 Okt 2026 |

**Dua fakta yang menyetir seluruh keputusan di bawah:**

- **Sisa ~7 hari ke freeze.** Apa pun yang dibangun harus selesai + teruji + sempat direkam sebelum 25–29 Sep.
- **Judging asinkron 8 hari.** Juri menonton **video (≤3 menit)** lalu **membuka repo/deploy sendiri**, kapan saja dalam 1–8 Okt. Konsekuensi keras: **fitur yang bergantung backend hidup bisa mati saat juri membukanya.** Yang aman menang: **live tampil di VIDEO (terekam), statis diandalkan di DEPLOY.**

## 2. Prinsip: dua bidang data yang TERPISAH

```
BIDANG STATIS  — di-FREEZE 25 Sep, ini yang dinilai, TAK BISA gagal
   runs/ → core/export/to_json.py → web/public/data → replay di frontend

BIDANG LIVE    — chat interaktif; menghasilkan jawaban saat itu juga
   Frontend ⇄ Middleware (WS/REST) ⇄ Agent (proses backend)
```

"Freeze data" mengunci **dataset yang dinilai**; **chat tetap bisa jalan** karena ia *menghasilkan* jawaban live (grounded ke data beku + probe live opsional), bukan mengubah dataset beku. Kalau middleware mati → frontend **turun anggun ke replay statis**. Aturan `[AD-1]` tidak dibuang, tapi **diperluas**: *"jalur yang DINILAI tidak pernah butuh runtime; chat live adalah bidang tambahan opsional."* Perubahan ini **wajib dicatat di `contracts/CHANGES.md` + disetujui bertiga.**

---

## 3. Tiga opsi plan

### Opsi 1 — Statis "feels-live" (tanpa backend) · ⭐ BASELINE WAJIB

Semua di client atas data statis. Nol proses backend.

- **#4** log aktivitas → penuh & nyata dari `runs/`.
- **#2** alur agent→mw→frontend → *replay streaming client-side* (mesin replay = "agen" semu). Bentuk terasa, tanpa server.
- **#3** chat → *walkthrough terskrip* atas transkrip: user tanya/klik → jawaban ditarik dari langkah + bukti. "Function calling" = tombol-tool yang membuka data transkrip (tampilkan bukti, lompat langkah, jelaskan momen).

**Rasional:** satu-satunya opsi yang **pasti selesai sebelum freeze**, **lolos gerbang eligibility**, dan **tak bisa gagal saat judging asinkron**. Sepenuhnya di lajur Web — tak menunggu siapa pun. **Ini harus ada apa pun yang terjadi.**

**Kekurangan:** chat tidak "bebas" — tak bisa menjawab pertanyaan di luar transkrip.

### Opsi 2 — Statis + middleware me-replay berkas (WS/HTTP)

Middleware hidup yang **streaming transkrip JSON** langkah-demi-langkah. Bentuk `Agent↔Middleware↔Frontend` **persis**, tapi "Agent" = mesin replay deterministik (baca file, bukan LLM).

**Rasional:** mendapat **bentuk arsitektur literal** yang diminta, tetap deterministik (secara logika tak bisa salah jawab). Bagus untuk membuktikan pipeline WS ke juri.

**Kekurangan:** butuh **proses backend hidup** → deploy tak lagi murni-statis; kalau middleware mati dalam window judging, fitur mati. Infra baru (host always-on).

### Opsi 3 — Hybrid live (statis + chat live sungguhan) · target penuh

Satu frontend, dua mode, degrade anggun (ada middleware+API key → live; tidak → replay statis).

- Bidang statis (Opsi 1) tetap jadi tulang punggung yang dinilai.
- **#2 & #3 live**: middleware menjalankan **agen Hamzah sungguhan** sebagai subprocess; **chat bebas + function calling = LLM runtime**, tiap tool-call dirender live.

**Rasional:** **cerita Track 1 terkuat** ("agen sungguhan, penalaran terlihat live") — **kalau** sempat & di-*hardening*. Paling ambisius.

**Kekurangan:** paling berat & berisiko dalam 7 hari; mengubah AD-1; menyentuh lajur Hamzah (agen) + infra Melco. **Hanya layak jika ditayangkan sebagai REKAMAN di video**, bukan diandalkan hidup di deploy selama 8 hari judging.

---

## 4. Rekomendasi

> **Ambil Opsi 1 sebagai baseline yang dikunci (pasti dikirim), lalu kejar Opsi 3-bagian-live HANYA untuk direkam di video.**

- **Yang diandalkan juri saat buka deploy** = statis (Opsi 1) → tak bisa gagal.
- **Yang bikin "wow" di video** = 1 skenario chat live (Opsi 3) → terekam, jadi aman walau backend belum production-grade.
- Opsi 2 (middleware replay) = jalan tengah kalau Opsi 3-live tak kekejar tapi masih mau bentuk WS literal.

Peta 4 note:

| Note | Bidang | Opsi | Pemilik utama | Wajib/Stretch |
| --- | --- | --- | --- | --- |
| #4 log aktivitas | statis | 1 | **Nadhilla** | **Wajib** |
| #2 agent→mw→frontend | statis→live | 1 (statis) / 3 (live) | Nadhilla + Hamzah/Melco | Wajib(statis)/Stretch(live) |
| #3 chat + func-call | live (bebas) | 3 | Hamzah (LLM) + Nadhilla (UI/mw) | Stretch |
| #1 agent automated | infra/cron | paralel | **Melco/Hamzah** | Wajib (bukti otonom) |

---

## 5. Arsitektur & pembagian pemilik

```
┌─────────────────────────────────────────────────────────────┐
│ FRONTEND (Next.js, web/)                          ← NADHILLA │
│  · replay statis (dinilai)  · panel chat  · live trail       │
│  · degrade anggun: middleware ada→live, tidak→statis         │
└───────────────┬─────────────────────────────────────────────┘
                │ WebSocket + REST (kontrak §6)
┌───────────────▼─────────────────────────────────────────────┐
│ MIDDLEWARE (baru, mis. FastAPI)      ← NADHILLA (API/orkestr)│
│  · endpoint chat & investigate  · streaming event            │
│  · manajemen sesi + pagu kredit  · fallback replay statis    │
└───────────────┬─────────────────────────────────────────────┘
                │ panggil pustaka
┌───────────────▼─────────────────────────────────────────────┐
│ AGENT (core/agent/)                               ← HAMZAH   │
│  · entrypoint streaming (yield langkah/tool-call)            │
│  · grounding + validator sitasi untuk jawaban chat           │
│           menggunakan CreditAwareClient          ← MELCO      │
└─────────────────────────────────────────────────────────────┘
```

**Catatan lajur:** middleware adalah komponen **baru**. Usul: **API & orkestrasi middleware dipegang Nadhilla** (karena ia jembatan ke frontend), **memanggil** `core/agent` (Hamzah) lewat entrypoint yang Hamzah sediakan, dan **CreditAwareClient** (Melco). Hosting middleware = Melco.

---

## 6. Kontrak Middleware (v0 — untuk disepakati sebelum coding)

Transport: **WebSocket** untuk streaming; **REST** untuk trigger & baca arsip.

```jsonc
// WS: client → server
{ "type": "chat.ask", "session": "…", "text": "kenapa FIXC waspada?" }
{ "type": "investigate", "symbol": "BBCA" }

// WS: server → client  (setiap event dirender live)
{ "type": "chat.token", "text": "…" }              // stream jawaban
{ "type": "tool.call",  "probe": "free_float", "args": {…} }   // agen memanggil tool
{ "type": "tool.result","evidence": { /* EvidenceEntry */ } }
{ "type": "step",       "step": 3, "finding": "confirmed", "credits_spent": 5 }
{ "type": "verdict",    "pantau_score": 74, "band": "waspada", "confidence": 0.83 }
{ "type": "error",      "reason": "pagu habis" }
{ "type": "done" }
```

```
REST
  GET  /activity?limit=50      → log aktivitas (juga bisa dibaca dari runs/ tanpa server)
  POST /investigate {symbol}   → memulai run; balasannya di-stream via WS
  GET  /health                 → untuk degrade anggun frontend
```

**Bentuk `EvidenceEntry` / `step` / `verdict` = persis `contracts/schemas.py`** supaya frontend memakai komponen yang sudah ada (reasoning trail, buku bukti) tanpa perubahan.

---

## 7. Task detail per orang

### 7A. NADHILLA (Web + Middleware API) — mulai SEKARANG

**Fase A · 18–22 Sep (statis, tak menunggu siapa pun):**
- [ ] **#4 Log aktivitas agen** — komponen dashboard membaca `runs/` (cron sweeps, investigasi, kredit) via `to_json` → `web/public/data/activity.json`. Feed bertanggal, ber-timestamp.
- [ ] **Chat walkthrough statis** — panel chat di halaman Investigasi: pertanyaan preset + input; jawaban ditarik dari langkah/bukti transkrip; "tool button" membuka bukti/lompat langkah. Nol backend.
- [ ] **Live trail component** — reasoning trail yang bisa distream (mode replay sekarang; nanti dipakai ulang untuk WS).
- [ ] **Finalisasi kontrak middleware §6** → kirim ke Hamzah/Melco.
- [ ] **Ajukan perubahan AD-1** di `contracts/CHANGES.md` (dua-bidang) untuk persetujuan.

**Fase B · 22–26 Sep (kalau live dikejar):**
- [ ] **Middleware shell** (FastAPI): endpoint `/health`, `/activity`, WS echo/replay → frontend nyambung ke mock dulu.
- [ ] **Client WS di frontend** + degrade anggun (`/health` → live/statis).
- [ ] Sambungkan panel chat ke event `chat.token`/`tool.call`/`step` sungguhan begitu agen Hamzah siap.

**Fase C · 27–29 Sep:** freeze `web/public/data`, gladi rekam, submit checklist.

### 7B. HAMZAH (Agent) — untuk jalur live (#2, #3)

- [ ] **Entrypoint streaming agen** — bungkus `investigator.py` agar *yield* event bertahap (`tool.call`, `tool.result`, `step`, `verdict`) alih-alih hanya transkrip final. Ini yang dipanggil middleware.
- [ ] **Mode chat/QA** — fungsi yang menjawab pertanyaan user **grounded ke buku bukti** (reuse `narrative/validate.py`): setiap angka wajib bersumber; gagal → tolak/template. **Nol kosakata saran finansial** (patuh vocab-guard).
- [ ] **Function-calling expose** — daftar tool (probe + `recall_history` + `show_evidence`) yang boleh dipanggil LLM saat chat, lewat `ProbeContext` yang ada.
- [ ] **Pagu chat** — batas kredit per sesi chat (reuse `agent/budget.py`) supaya tidak jebol.
- [ ] **(#1)** Bantu cron investigasi tahap-2 menulis transkrip nyata ke `runs/investigations/` — ini juga mengisi bidang statis.

### 7C. MELCO (Ingest + Infra) — untuk otonom (#1) & hosting

- [ ] **(#1) Cron investigasi otomatis** — `.github/workflows/` menjalankan agen atas watchlist harian, commit `runs/investigations/` (bukti otonom ber-timestamp) → mengisi dashboard #4.
- [ ] **Hosting middleware** — host always-on kecil (Railway/Fly/VM) untuk demo live; env `SECTORS_API_KEY` + `ANTHROPIC_API_KEY`. **Bukan Vercel** (Vercel tetap untuk frontend statis).
- [ ] **CreditAwareClient utk middleware** — pastikan agen di middleware tetap lewat gateway termeter (ledger `data/credit_ledger.jsonl`).
- [ ] **(opsional) `to_json` di CI** — setelah cron commit `runs/`, jalankan `to_json` + commit `web/public/data/` → frontend statis auto-update.

---

## 8. Risiko & mitigasi

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Live backend mati saat judging asinkron | Fitur chat mati di deploy | Chat live **ditayangkan di VIDEO**; deploy pakai **fallback walkthrough statis** |
| Tak kekejar sebelum freeze 25 Sep | Live tak jadi | **Opsi 1 sudah cukup** untuk penilaian; live = stretch murni |
| Chat mengarang / beri saran | **Diskualifikasi** | Grounding wajib sitasi + vocab-guard + "bukan saran investasi" |
| Pagu kredit jebol karena chat | Fatal | Batas kredit per sesi + cache jawaban umum |
| AD-1 diubah diam-diam | Rusak kepercayaan tim | Catat di `contracts/CHANGES.md`, sepakat bertiga dulu |

## 9. Keputusan yang harus diambil bertiga (sebelum coding live)

1. **Kunci Opsi 1 sebagai baseline?** (rekomendasi: ya, mulai sekarang)
2. **Kejar Opsi 3-live untuk video?** ya/tidak — kalau ya, Hamzah sanggup entrypoint stream sebelum ~24 Sep?
3. **Siapa host middleware & apakah AD-1 diperluas** (dua-bidang) → catat di `contracts/CHANGES.md`.
4. Kalau ragu waktu → **potong live, kirim Opsi 1**; jangan pertaruhkan submission.
