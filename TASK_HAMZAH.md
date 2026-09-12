# TASK_HAMZAH.md — Agen, Skoring & Eval

**Lajur: inti Track 1.** Ini bagian yang dinilai juri sebagai *"custom agent logic or orchestration"*, dan bagian yang paling menentukan menang atau tidak.
Misi satu kalimat: **membuat agen yang memutuskan bukti mana yang layak dibeli — dan membuktikan keputusannya bernilai.**

Master plan: [`TASK.md`](TASK.md) · Desain: [`ARCHITECTURE.md`](ARCHITECTURE.md) §3 · Alasan: [`RESEARCH.md`](RESEARCH.md)
Tugas di file ini **termasuk QA-nya sendiri**. Video & submission dikerjakan bareng di akhir.

---

## Status · 12 Sep 2026 (malam)

| Fase | Status |
| --- | --- |
| H1 skoring | ✅ selesai — `core/scoring/` + 10 tes |
| H1 kalibrasi | ⚠️ **selesai sejauh yang mungkin** — terkalibrasi 4 dari 6 komponen, lihat bawah |
| H2 agen | ✅ selesai — tiga tahap + memori + pagar, 29 tes |
| H2 narasi | ✅ selesai — 43 tes, termasuk penolakan halusinasi angka **dan emiten** |
| **H3 eval agen** | ✅ **selesai** — Angka 2 ada, tapi hasilnya membantah salah satu klaim kami. `reports/agent-eval-ringkasan.md` |
| H4 dukungan | 🔄 berjalan |

**315 tes lolos** tanpa jaringan dan tanpa kunci API. ruff, `contracts/check.py`, dan
`vocab_guard` bersih. PR: [#4](https://github.com/hamzadlnitb/sectors2026/pull/4).

### ✅ Penghambat 10 Sep sudah terjawab — dan jawabannya bukan yang gua duga

Gua kira Angka 1 terhambat backfill. Setelah Melco menarik data sungguhnya
(`contracts/CHANGES.md` C4) dan gua verifikasi dengan menjalankan probe pada dua tanggal
acuan, ternyata **sebagian penghambat itu permanen dan sebagian lagi tidak pernah ada.**

**Permanen:** `fetch-free-float` tidak mengirim tanggal berlaku. Free float lampau tidak
ada di mana pun dan tidak bisa dibeli dengan kredit berapa pun. FFS **tidak akan pernah**
ikut kalibrasi historis. BCI bisa ditarik per tanggal, tapi populasi positif (18 emiten)
tetap di bawah ambang 30.

→ Angka 1 dilaporkan apa adanya: **terkalibrasi atas 4 dari 6 komponen** (VAS, PFD, FRD,
SSS). Bobot FFS + BCI = 0,43 tetap prior domain, dinyatakan terbuka di
`reports/validation.md`, `core/scoring/weights.py`, dan wajib muncul di halaman Metodologi.

**Tidak pernah ada:** Angka 2 berjalan pada `as_of` terkini, dan di sana **keenam probe
hidup**. H3 tidak pernah benar-benar terhambat backfill historis.

| Probe | `as_of` 2026-08-20 | `as_of` 2026-09-11 |
| --- | --- | --- |
| `free_float` | n/a | 94 |
| `broker_concentration` | n/a | 38 |
| `volume_anomaly` | 100 | 16 |

Satu-satunya prasyarat tersisa untuk H3: `broker_summary` terkini diperluas dari 16 ke 39
emiten (±46 kredit, sudah masuk `TASK_MELCO.md` M7 versi koreksi). Eval bisa mulai
sekarang atas 16 emiten yang sudah ada, lalu diperluas.

### Tanggapan atas C4 — sudah diberikan
C4 **diterima**, tercatat sebagai `contracts/CHANGES.md` **C5**. Tidak ada pembatalan.

### Penghambat lama (10 Sep) — disimpan sebagai jejak keputusan

`broker_summary` dan `free_float` masing-masing hanya punya **satu tanggal** di warehouse
(2026-09-07), yang jatuh sesudah sebagian besar titik T-k. Setelah saringan point-in-time,
**BCI + FFS — 0,43 dari total bobot — tidak pernah terisi sekali pun.**

Akibatnya: hanya 9 positif yang bisa dinilai, semuanya dalam rentang tiga minggu; bobot
sekarang adalah prior domain bertanda `cal-2026-09-10-sementara`; dan angka validasi yang
ada membuktikan pipa hitungnya jalan, **bukan performa yang boleh dikutip di video**.

Ini juga menghambat H3: eval agen butuh probe yang benar-benar bisa jalan pada banyak
emiten. Kebutuhan data ada di `reports/validation.md`; tugasnya sudah masuk
`TASK_MELCO.md` M7.

### Temuan yang mengubah kontrak dan berkas orang lain
- `contracts/CHANGES.md` **C2** — dua invarian `check.py` menolak transkrip yang sah
- `contracts/CHANGES.md` **C3** — validator narasi tidak memeriksa nama emiten
- `requirements.txt` mempin numpy/pandas tanpa wheel untuk Python 3.13 (CI dan `.venv`
  pakai 3.12 jadi aman, tapi `make setup` gagal di `python3` sistem) — keputusan tim

---

## Milik lu

```
core/agent/       planner.py · investigator.py · adjudicator.py
                  budget.py · guardrails.py · memory.py · transcript.py
core/scoring/     composite.py · facts.py
core/narrative/   generate.py · validate.py
evals/            agent_eval.py · cases.yaml
notebooks/calibration.ipynb · reports/validation.md
tests/agent/ · tests/scoring/ · tests/narrative/
```

**Jangan sentuh:** `core/sectors/`, `core/ingest/`, `core/probes/`, `data/`, `.github/`, `Makefile` (Melco) · `web/`, `core/export/`, `fixtures/` (Nadhilla).

## Kontrak lu

**Lu mengonsumsi** — dari Melco: antarmuka `Probe` (`cost_estimate()`, `run() -> ProbeResult`), warehouse parquet, `registry.py`, `docs/endpoint-costs.md`, dan (kalau jadi) `catalog.py`.

**Lu menghasilkan** — dipakai Nadhilla: `InvestigationTranscript` JSON sesuai `ARCHITECTURE.md` §10. Nadhilla membangun UI langsung di atas bentuk ini.

✅ **`InvestigationTranscript` sudah beku** di `contracts/schemas.py`, dan tiga fixture sudah mencerminkannya persis. Catat `Step.budget_granted` — pagu tambahan yang dikabulkan saat eskalasi **wajib** dicatat, karena `check.py` menelusuri aritmetika pagu langkah demi langkah dan akan menolak yang tidak nyambung.

⚠️ Butuh bentuknya berubah? Ajukan di [`contracts/CHANGES.md`](contracts/CHANGES.md) — **jangan** edit `schemas.py` langsung. Kalau bentuk berubah setelah ada transkrip beredar, naikkan `schema_version`.

🔓 **Lu tidak boleh menunggu Melco.** Pakai `core/probes/stubs.py` dan `fixtures/warehouse-mini/` sejak hari ini, ganti ke probe asli satu per satu begitu Melco mengabari.

---

## Fase

### H1 · Skoring & kalibrasi — Angka 1 · 9–12 Sep
> Bobot komposit harus keluar dari data, bukan dari tebakan. Ini prasyarat agen bisa dinilai.

- [x] `scoring/facts.py` — buku bukti: nilai + endpoint + params + `as_of` `[T12]`
- [x] `scoring/composite.py` — pembobotan, band 0/30/60/80, dan **tingkat keyakinan** (berapa bobot yang tercakup, karena agen boleh berhenti lebih awal) `ARCHITECTURE.md` §4
- [x] Bangun **himpunan positif** dari suspensi (saring alasan terkait pergerakan/aktivitas tidak wajar) — data mentahnya dari Melco M3
- [x] Bangun **himpunan kontrol** tersamakan (kapitalisasi + subsektor)
- [x] Hitung enam sub-skor pada **T-1 / T-3 / T-5 / T-10** hari bursa — **strictly point-in-time, nol lookahead**
- [x] Cari bobot: logistic regression atau grid search. Pilih yang bisa dijelaskan dalam 15 detik di video
- [x] Split waktu: kalibrasi 18 bulan pertama, uji 6 bulan terakhir yang belum pernah dilihat
- [x] `reports/validation.md` **Angka 1** — Precision@20, recall pada ambang ≥60, **median lead time**, plus **batasan yang diakui terbuka** `[T6][T7]`
- [ ] **QA:** tes anti-lookahead (skor pada T-5 tidak boleh berubah kalau data setelah T-5 dihapus) · komponen hilang → skor tetap keluar dengan keyakinan turun, bukan crash

### H2 · Agen · 11–18 Sep · ★ inti Track 1
> ✅ **Gerbang: `make investigate` jalan end-to-end paling lambat 18 Sep.**

- [x] `agent/planner.py` — dari sinyal Tier-1 + memori → hipotesis, probe terurut, permintaan pagu kredit. Keluaran **JSON terstruktur**, tidak pernah prosa bebas
- [x] `agent/investigator.py` — loop: eksekusi probe → evaluasi temuan (`confirmed` / `refuted` / `inconclusive`) → `continue` / `escalate` / `conclude`
- [x] `agent/budget.py` — pagu per-investigasi (25 kredit) & per-hari. Eskalasi **bisa ditolak**, dan agen harus tetap menyimpulkan dengan bukti seadanya
- [x] `agent/guardrails.py` — maks 8 langkah, timeout per langkah, validasi skema, satu probe hanya sekali per investigasi, penutupan aman saat pagar tertembus `[AD-6]`
- [x] `agent/memory.py` — riwayat per-ticker di DuckDB; investigasi ulang menghasilkan **rencana berbeda** yang diarahkan ke apa yang berubah
- [x] `agent/transcript.py` — transkrip yang bisa diputar ulang, sesuai kontrak
- [x] `agent/adjudicator.py` — buku bukti → **skor deterministik** → narasi
- [x] `narrative/generate.py` — Claude menyusun 3–4 kalimat Bahasa Indonesia **hanya dari buku bukti**
- [x] `narrative/validate.py` — tiap token angka wajib punya padanan di buku bukti; gagal → **fallback template deterministik** `[AD-4]`
- [x] `make investigate SYMBOL=XXXX` jalan end-to-end
- [ ] **QA:** buku bukti dipalsukan → validator menolak · agen ngelantur → pagar menutup aman · pagu habis → putusan berkeyakinan rendah, bukan crash · keluaran LLM tidak sesuai skema → retry lalu fallback · narasi lolos larangan kosakata CI Melco

> **Empat perilaku yang wajib terlihat di transkrip**, karena inilah pembeda agen dari if-else berbaju LLM: **perutean adaptif** (membuka jalur bukti di luar rencana awal), **penghentian dini** (berhenti begitu cukup), **eskalasi** (minta tambahan pagu dengan alasan tertulis), **memori** (investigasi ulang berbeda rencananya). Pastikan ada di transkrip **dan** bisa ditunjuk di video. `ARCHITECTURE.md` §3

### H3 · Eval agen — Angka 2 · 19–21 Sep 🔴 ← **PEKERJAAN BERIKUTNYA**
> **Gerbang keras tim.** Kalau agen tidak mengalahkan urutan tetap, klaim utama kita runtuh dan kita **harus tahu sebelum merekam video**, bukan sesudah.

> ⚠️ Sub-agent yang menggarap ini stall sebelum menghasilkan berkas. `evals/` masih kosong.
> Rancangannya sudah matang di `ARCHITECTURE.md` §6, tinggal ditulis.
>
> ✅ **Harness selesai 12 Sep.** `evals/arms.py` (empat lengan + pembanding kelima
> tanpa-harga), `evals/build_cases.py` (alam semesta dari warehouse, **16 emiten** —
> di bawah sasaran 30–50 karena warehouse memang baru memuat sebanyak ini),
> `evals/agent_eval.py` (metrik + laporan), 13 tes.
>
> Satuan biayanya **kredit terhitung** (`cost_estimate`), bukan kredit terbakar: eval
> jalan dengan `client=None` sehingga nol kredit benar-benar dibelanjakan. Kredit
> terbakar akan mengukur keberuntungan cache, bukan kualitas perencanaan.
>
> ✅ **Peringatan 10 Sep dicabut.** Gua sempat menulis "jangan jalankan eval sebelum backfill
> mendarat" — itu keliru. Eval berjalan pada `as_of` terkini, dan di sana keenam probe hidup.
> Yang tersisa hanya memperluas `broker_summary` terkini dari 16 ke 39 emiten (±46 kredit)
> supaya alam semesta evalnya cukup lebar. Mulai sekarang atas 16 emiten yang ada.

- [x] `evals/cases.yaml` — 30–50 ticker uji: campuran normal, mencurigakan, dan yang benar-benar pernah disuspend
- [x] `evals/agent_eval.py` — empat jalur: **agen** vs **menyeluruh** vs **urutan tetap** vs **acak berpagu sama**
- [x] Ukur: kredit per investigasi · kesepakatan band vs menyeluruh · presisi eskalasi (ketika agen membuka probe di luar rencana, seberapa sering itu mengubah band)
- [x] **Ukur pemilihan tool sadar biaya** `[AD-7]` — perencana yang melihat katalog MCP **beserta harganya** vs katalog yang harganya disembunyikan. Ini yang membuktikan klaim MCP kita punya isi
- [x] `reports/validation.md` **Angka 2** — target: penghematan kredit **≥50%** dengan kesepakatan band **≥90%**
- [x] Kunci satu kalimat untuk video: *"investigasi menyeluruh butuh N kredit; perencana kami rata-rata Y, dan sepakat Z% dari waktu"*
- [x] Target meleset → jalankan mitigasi `ARCHITECTURE.md` §11 baris pertama, **hari itu juga**

### H4 · Dukungan & jaga · 21–25 Sep
- [ ] Serahkan transkrip asli ke Nadhilla untuk menggantikan fixture
- [x] Bantu Melco menyambungkan agen ke cron tahap 2 (±19 Sep)
- [ ] Perbaiki hanya masalah yang muncul **berulang** di user testing; sisanya ke `reports/feedback.md`
- [ ] Isi bagian metodologi (rumus, bobot, dua angka, batasan) — Nadhilla yang merender

---

## Prinsip yang tidak boleh dilanggar

**Agen memutuskan APA yang diselidiki. Kode memutuskan BERAPA skornya.** `[AD-4][K8]`
LLM: menyusun rencana, memilih probe, memutuskan lanjut/berhenti, menulis narasi.
Kode: menghitung tiap sub-skor, membobot komposit, menetapkan band.
Kalau batas ini kabur, angka jadi bisa dikarang dan kredibilitas kita habis di depan juri praktisi pasar.

**Anggaran LLM terpisah dari kredit Sectors** `[K9]`. Cache transkrip berkunci `(ticker, tanggal, versi_prompt)`. Jalankan eval pakai model kecil sampai perilakunya stabil, baru naikkan.

## Gerbang yang lu pegang
| Tanggal | Gerbang | Status |
| --- | --- | --- |
| 12 Sep | Angka 1 ada di `reports/validation.md` | ✅ ada, cakupannya dinyatakan terbuka (4 dari 6) |
| 18 Sep | `make investigate` jalan end-to-end | ✅ **selesai 10 Sep**, delapan hari lebih awal |
| **21 Sep** | 🔴 **Angka 2 ada — atau klaim diubah hari itu juga** | ❌ belum mulai, **tidak terhambat** — ini pekerjaan berikutnya |

## Kalau lu terblokir
Melco telat → tetap jalan pakai stub, jangan menunggu. Waktu habis di H2 → potong **memori agen** lebih dulu (perencana + penyelidik + penilai sudah cukup memenuhi syarat Track 1); jangan potong eval, karena tanpa Angka 2 kita kehilangan pembeda. Batas keputusan **18 Sep**.

## Selesai kalau
`make investigate SYMBOL=XXXX` menghasilkan transkrip lengkap · empat perilaku agentik terlihat di transkrip · validator menolak buku bukti palsu · `evals/` memuat ablasi empat jalur · `reports/validation.md` memuat **dua angka** beserta batasannya.
