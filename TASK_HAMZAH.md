# TASK_HAMZAH.md — Agen, Skoring & Eval

**Lajur: inti Track 1.** Ini bagian yang dinilai juri sebagai *"custom agent logic or orchestration"*, dan bagian yang paling menentukan menang atau tidak.
Misi satu kalimat: **membuat agen yang memutuskan bukti mana yang layak dibeli — dan membuktikan keputusannya bernilai.**

Master plan: [`TASK.md`](TASK.md) · Desain: [`ARCHITECTURE.md`](ARCHITECTURE.md) §3 · Alasan: [`RESEARCH.md`](RESEARCH.md)
Tugas di file ini **termasuk QA-nya sendiri**. Video & submission dikerjakan bareng di akhir.

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

- [ ] `scoring/facts.py` — buku bukti: nilai + endpoint + params + `as_of` `[T12]`
- [ ] `scoring/composite.py` — pembobotan, band 0/30/60/80, dan **tingkat keyakinan** (berapa bobot yang tercakup, karena agen boleh berhenti lebih awal) `ARCHITECTURE.md` §4
- [ ] Bangun **himpunan positif** dari suspensi (saring alasan terkait pergerakan/aktivitas tidak wajar) — data mentahnya dari Melco M3
- [ ] Bangun **himpunan kontrol** tersamakan (kapitalisasi + subsektor)
- [ ] Hitung enam sub-skor pada **T-1 / T-3 / T-5 / T-10** hari bursa — **strictly point-in-time, nol lookahead**
- [ ] Cari bobot: logistic regression atau grid search. Pilih yang bisa dijelaskan dalam 15 detik di video
- [ ] Split waktu: kalibrasi 18 bulan pertama, uji 6 bulan terakhir yang belum pernah dilihat
- [ ] `reports/validation.md` **Angka 1** — Precision@20, recall pada ambang ≥60, **median lead time**, plus **batasan yang diakui terbuka** `[T6][T7]`
- [ ] **QA:** tes anti-lookahead (skor pada T-5 tidak boleh berubah kalau data setelah T-5 dihapus) · komponen hilang → skor tetap keluar dengan keyakinan turun, bukan crash

### H2 · Agen · 11–18 Sep · ★ inti Track 1
> ✅ **Gerbang: `make investigate` jalan end-to-end paling lambat 18 Sep.**

- [ ] `agent/planner.py` — dari sinyal Tier-1 + memori → hipotesis, probe terurut, permintaan pagu kredit. Keluaran **JSON terstruktur**, tidak pernah prosa bebas
- [ ] `agent/investigator.py` — loop: eksekusi probe → evaluasi temuan (`confirmed` / `refuted` / `inconclusive`) → `continue` / `escalate` / `conclude`
- [ ] `agent/budget.py` — pagu per-investigasi (25 kredit) & per-hari. Eskalasi **bisa ditolak**, dan agen harus tetap menyimpulkan dengan bukti seadanya
- [ ] `agent/guardrails.py` — maks 8 langkah, timeout per langkah, validasi skema, satu probe hanya sekali per investigasi, penutupan aman saat pagar tertembus `[AD-6]`
- [ ] `agent/memory.py` — riwayat per-ticker di DuckDB; investigasi ulang menghasilkan **rencana berbeda** yang diarahkan ke apa yang berubah
- [ ] `agent/transcript.py` — transkrip yang bisa diputar ulang, sesuai kontrak
- [ ] `agent/adjudicator.py` — buku bukti → **skor deterministik** → narasi
- [ ] `narrative/generate.py` — Claude menyusun 3–4 kalimat Bahasa Indonesia **hanya dari buku bukti**
- [ ] `narrative/validate.py` — tiap token angka wajib punya padanan di buku bukti; gagal → **fallback template deterministik** `[AD-4]`
- [ ] `make investigate SYMBOL=XXXX` jalan end-to-end
- [ ] **QA:** buku bukti dipalsukan → validator menolak · agen ngelantur → pagar menutup aman · pagu habis → putusan berkeyakinan rendah, bukan crash · keluaran LLM tidak sesuai skema → retry lalu fallback · narasi lolos larangan kosakata CI Melco

> **Empat perilaku yang wajib terlihat di transkrip**, karena inilah pembeda agen dari if-else berbaju LLM: **perutean adaptif** (membuka jalur bukti di luar rencana awal), **penghentian dini** (berhenti begitu cukup), **eskalasi** (minta tambahan pagu dengan alasan tertulis), **memori** (investigasi ulang berbeda rencananya). Pastikan ada di transkrip **dan** bisa ditunjuk di video. `ARCHITECTURE.md` §3

### H3 · Eval agen — Angka 2 · 19–21 Sep 🔴
> **Gerbang keras tim.** Kalau agen tidak mengalahkan urutan tetap, klaim utama kita runtuh dan kita **harus tahu sebelum merekam video**, bukan sesudah.

- [ ] `evals/cases.yaml` — 30–50 ticker uji: campuran normal, mencurigakan, dan yang benar-benar pernah disuspend
- [ ] `evals/agent_eval.py` — empat jalur: **agen** vs **menyeluruh** vs **urutan tetap** vs **acak berpagu sama**
- [ ] Ukur: kredit per investigasi · kesepakatan band vs menyeluruh · presisi eskalasi (ketika agen membuka probe di luar rencana, seberapa sering itu mengubah band)
- [ ] **Ukur pemilihan tool sadar biaya** `[AD-7]` — perencana yang melihat katalog MCP **beserta harganya** vs katalog yang harganya disembunyikan. Ini yang membuktikan klaim MCP kita punya isi
- [ ] `reports/validation.md` **Angka 2** — target: penghematan kredit **≥50%** dengan kesepakatan band **≥90%**
- [ ] Kunci satu kalimat untuk video: *"investigasi menyeluruh butuh N kredit; perencana kami rata-rata Y, dan sepakat Z% dari waktu"*
- [ ] Target meleset → jalankan mitigasi `ARCHITECTURE.md` §11 baris pertama, **hari itu juga**

### H4 · Dukungan & jaga · 21–25 Sep
- [ ] Serahkan transkrip asli ke Nadhilla untuk menggantikan fixture
- [ ] Bantu Melco menyambungkan agen ke cron tahap 2 (±19 Sep)
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
| Tanggal | Gerbang |
| --- | --- |
| 12 Sep | Angka 1 ada di `reports/validation.md` |
| 18 Sep | `make investigate` jalan end-to-end |
| **21 Sep** | 🔴 **Angka 2 ada — atau klaim diubah hari itu juga** |

## Kalau lu terblokir
Melco telat → tetap jalan pakai stub, jangan menunggu. Waktu habis di H2 → potong **memori agen** lebih dulu (perencana + penyelidik + penilai sudah cukup memenuhi syarat Track 1); jangan potong eval, karena tanpa Angka 2 kita kehilangan pembeda. Batas keputusan **18 Sep**.

## Selesai kalau
`make investigate SYMBOL=XXXX` menghasilkan transkrip lengkap · empat perilaku agentik terlihat di transkrip · validator menolak buku bukti palsu · `evals/` memuat ablasi empat jalur · `reports/validation.md` memuat **dua angka** beserta batasannya.
