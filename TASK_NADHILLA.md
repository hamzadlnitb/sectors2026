# TASK_NADHILLA.md — Web & Lapisan Ekspor

**Lajur: yang dilihat juri.** Video menyumbang 30% nilai, dan hampir seluruh isinya adalah layar yang lu bangun. Kalau agen Hamzah tidak terlihat berpikir di layar, kerja timnya tidak terbaca.
Misi satu kalimat: **membuat penalaran agen bisa ditonton — dan tidak pernah gagal saat direkam.**

Master plan: [`TASK.md`](TASK.md) · Desain: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Alasan: [`RESEARCH.md`](RESEARCH.md)
Tugas di file ini **termasuk QA-nya sendiri**. Video & submission dikerjakan bareng di akhir — lu menyiapkan layarnya, bukan merekamnya sendirian.

---

## Milik lu

```
web/              app/investigasi/ · app/papan/ · app/metodologi/
                  components/ · public/data/
core/export/      to_json.py
fixtures/         transcripts/{normal,waspada,eskalasi}.json · warehouse-mini/
tests/web/ · tests/export/
```

**Jangan sentuh:** `core/sectors/`, `core/ingest/`, `core/probes/`, `data/`, `.github/`, `Makefile` (Melco) · `core/agent/`, `core/scoring/`, `core/narrative/`, `evals/` (Hamzah).

## Kontrak lu

**Lu mengonsumsi:** `InvestigationTranscript` JSON dari Hamzah — bentuknya di `ARCHITECTURE.md` §10.

**Lu menghasilkan:** aplikasi ter-deploy + `core/export/to_json.py` yang menulis `web/public/data/` dan `runs/`.

🔓 **Lu tidak boleh menunggu Hamzah.** Fixture dibekukan hari ini, dan **lu yang memiliki `fixtures/`** — jadi lu bisa membangun seluruh UI dari hari pertama, lalu tukar ke transkrip asli sekitar 18 Sep tanpa mengubah satu baris komponen pun.

> Kalau lu perlu bentuk transkrip berubah, ajukan di [`contracts/CHANGES.md`](contracts/CHANGES.md) — jangan edit `core/agent/` maupun `schemas.py`. Kontrak beku total setelah 12 Sep.
>
> Bentuk yang perlu lu render sudah lengkap: `Step.budget_granted` (hasil eskalasi), `narrative_source` (`template` = validator menolak keluaran LLM, tampilkan apa adanya), `confidence`, `credits_total` vs `baseline_credits`, dan `memory_ref` yang menunjuk `runs/investigations/<memory_ref>.json`.

---

## Fase

### N1 · Fondasi & fixture · 8–10 Sep
- [x] Bareng tim: bekukan `InvestigationTranscript`, lalu tulis **tiga fixture** yang mewakili tiga keadaan UI yang berbeda: `normal.json` (agen berhenti setelah 2 langkah), `waspada.json` (investigasi penuh), `eskalasi.json` (agen membuka probe di luar rencana). Tanpa ketiganya, UI lu cuma teruji di satu jalur
- [ ] Next.js 15 App Router + Tailwind + Recharts, deploy Vercel kosong hari ini juga — supaya masalah deploy ketahuan sekarang, bukan tanggal 25
- [x] `core/export/to_json.py` — kontrak tulis ke `web/public/data/` dan `runs/`
- [x] **Aturan mati:** web **hanya membaca JSON statis**. Nol panggilan Sectors API, nol panggilan LLM saat runtime `[AD-1]`. Ini yang membuat demo tidak bisa gagal

### N2 · Halaman Investigasi · 10–16 Sep · ★ layar utama video
> Ini satu-satunya layar yang membuktikan ada agen di balik produk. Kerjakan paling serius.

- [x] **Putar ulang transkrip langkah demi langkah** — bukan menampilkan hasil akhir. Penonton harus melihat: rencana awal (hipotesis + probe terurut + pagu kredit), lalu tiap langkah muncul berurutan dengan temuannya, lalu putusan
- [x] Tandai jelas **empat momen agentik** — ini yang dinilai Track 1 `ARCHITECTURE.md` §3:
      · **perutean adaptif** — agen membuka probe di luar rencana awal
      · **penghentian dini** — agen berhenti karena bukti sudah cukup, dan hemat berapa kredit
      · **eskalasi** — agen minta tambah pagu, beserta alasan tertulisnya
      · **memori** — investigasi ulang menghasilkan rencana berbeda
- [x] Skor besar + band + **tingkat keyakinan** + **kredit terpakai vs baseline menyeluruh** (angka ini klaim utama tim, jangan dikubur di pojok)
- [ ] Kontrol putar ulang: jeda, mundur, lompat ke langkah. Juri menonton asinkron dan akan mengulang
- [ ] **QA:** ketiga fixture render benar · transkrip 2 langkah dan 8 langkah sama rapinya · `finding: refuted` dan `inconclusive` punya tampilan sendiri, bukan diperlakukan seperti `confirmed`

### N3 · Buku Bukti · 14–18 Sep
- [x] Tiap angka di narasi **bisa diklik** → endpoint Sectors + parameter + `as_of` `[T12]`
- [x] Tampilkan biaya kredit tiap entri bukti
- [x] Tandai jelas kalau narasi jatuh ke **template deterministik** (artinya validator Hamzah menolak keluaran LLM) — kejujuran ini justru menambah kredibilitas
- [ ] **QA:** tidak ada angka di narasi yang tidak punya entri bukti · `as_of` selalu tampil, karena data Sectors EOD dan kita harus jujur soal keterlambatan `[K7]`

### N4 · Papan Waspada & Metodologi · 16–22 Sep
- [ ] **Papan Waspada** — arsip investigasi otonom bertanggal, bisa ditelusuri mundur. Ini membuat bukti unattended run terlihat **di dalam produk**, bukan cuma di repo `[T5]`
- [ ] **Metodologi** — rumus enam komponen, bobot hasil kalibrasi, **dua angka validasi**, dan **batasan yang diakui terbuka**. Isinya dari Hamzah, lu yang merender `[T6][T7]`
- [ ] Disclaimer permanen di setiap halaman: *"PANTAU adalah alat informasi dan analisis, bukan saran investasi."* `[K5]`
- [ ] **Nol kosakata saran finansial** di seluruh teks UI — "beli", "jual", "target harga", "rekomendasi", "cuan", "pasti naik". CI Melco akan menangkapnya, tapi jangan sampai ketahuan CI duluan

### N5 · Lokalisasi & mobile · 18–22 Sep
- [ ] Bahasa Indonesia penuh, format IDR, tanggal & jam WIB, kalender bursa `[T14]`
- [ ] **Mobile-first** — persona kita pegang HP di angkot, bukan Bloomberg terminal `[T1]`
- [ ] Tukar fixture → transkrip asli dari Hamzah (±18 Sep). Kalau ada yang pecah di sini, berarti kontraknya bocor — laporkan, jangan tambal diam-diam
- [ ] **QA:** uji di HP asli, bukan cuma devtools · teks panjang Bahasa Indonesia tidak merusak layout · halaman tetap terbaca saat transkrip minimal

### N6 · Siap rekam · 22–25 Sep
- [ ] Pilih 3–4 ticker yang **menceritakan sesuatu**: satu normal (agen berhenti cepat), satu waspada penuh, satu dengan eskalasi, satu investigasi ulang yang menunjukkan memori
- [ ] Pra-muat semua state. **Nol pemuatan lambat di depan kamera** `[T9]`
- [ ] Buang setiap komponen yang pernah goyah saat dicoba — kelihatan rapi mengalahkan kelihatan lengkap `[T9]`
- [ ] Verifikasi URL Vercel dari **incognito dan HP**, bukan dari laptop yang sudah login
- [ ] 🔒 **Feature freeze 25 Sep** — setelah ini hanya bugfix

---

## Gerbang yang lu pegang
| Tanggal | Gerbang |
| --- | --- |
| 10 Sep | Tiga fixture beku + Vercel hidup |
| 16 Sep | Halaman investigasi memutar ulang fixture dengan benar |
| 22 Sep | Produk end-to-end pakai transkrip asli, ter-deploy publik |
| 25 Sep | 🔒 Siap rekam |

## Kalau lu terblokir
Hamzah telat → tetap jalan pakai fixture, itu memang gunanya. Bentuk transkrip berubah → minta Hamzah, jangan edit `core/agent/`. Waktu menipis → potong **Papan Waspada** lebih dulu (arsipnya tetap ada di repo sebagai bukti); **jangan potong halaman investigasi**, karena itu satu-satunya layar yang membuktikan ada agen.

## Selesai kalau
`make demo` membuka aplikasi tanpa API key · halaman investigasi memutar transkrip asli langkah demi langkah dengan empat momen agentik tertandai · tiap angka bisa diklik ke sumbernya · metodologi memuat dua angka dan batasannya · jalan mulus di HP · nol panggilan API dan LLM saat runtime.
