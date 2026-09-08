# PANTAU

**Agen investigasi risiko manipulasi & likuiditas saham IDX.**
Sectors Hackathon 2026 · Track 1 — AI Agents & Assistants

> Untuk investor ritel IDX yang menerima rekomendasi saham dari grup Telegram dan TikTok,
> PANTAU adalah agen yang menyelidiki satu saham seperti analis sungguhan — memutuskan
> sendiri bukti apa yang layak dikejar, lalu menjawab satu pertanyaan yang tidak bisa
> dijawab aplikasi sekuritas mana pun: *"saham ini lagi ramai — ini nyata atau digoreng?"*

Agen ada di sini karena data Sectors mahal dan jatah kami 1.000 kredit: yang sulit bukan
menghitung skor, tapi memutuskan **bukti mana yang layak dibeli untuk saham ini, hari ini**.

**PANTAU adalah alat informasi dan analisis, bukan saran investasi.**

---

## Dokumen

| File | Isi |
| --- | --- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Desain sistem, enam komponen skor, anggaran kredit, keputusan arsitektur |
| [`TASK.md`](TASK.md) | Rencana eksekusi, gerbang lintas-lajur, anggaran kredit, rencana cadangan |
| [`TASK_MELCO.md`](TASK_MELCO.md) | Lajur data, transport & probe |
| [`TASK_HAMZAH.md`](TASK_HAMZAH.md) | Lajur agen, skoring & eval |
| [`TASK_NADHILLA.md`](TASK_NADHILLA.md) | Lajur web & lapisan ekspor |
| [`RESEARCH.md`](RESEARCH.md) | Aturan & rubrik lomba, riset pemenang hackathon internasional, daftar jangan-dibangun |
| [`SUBMISSION.md`](SUBMISSION.md) | Checklist freeze untuk hari submit |

## Status

🚧 Dalam pembangunan, tiga lajur paralel. Lihat `TASK.md`.

| Lajur | Isi | Status |
| --- | --- | --- |
| Data, Transport & Probe | gateway kredit, warehouse, enam probe, ingest, cron, CI | fondasi jalan — lihat di bawah |
| Agen, Skoring & Eval | perencana, penyelidik, penilai, kalibrasi, ablasi | belum |
| Web & Lapisan Ekspor | halaman investigasi, buku bukti, papan waspada | belum |

**Yang sudah bisa dijalankan hari ini, tanpa API key:** `make demo` menjalankan
enam probe atas warehouse yang di-commit; `make test` menjalankan 182 tes tanpa
menyentuh jaringan sama sekali.

⚠️ **Belum ada satu pun biaya endpoint yang terukur.** Angka kredit di
[`docs/endpoint-costs.md`](docs/endpoint-costs.md) masih asumsi sampai
`make spike` dijalankan dengan API key. Kolom *Status* di dokumen itu
mengatakannya per baris.

## Quickstart

Tanpa kredensial apa pun:

```bash
git clone <repo> && cd sectors2026
make setup
make demo      # enam probe atas snapshot yang di-commit, nol jaringan
```

```bash
make probes    # daftar alat agen + harga kreditnya
make credits   # posisi ledger kredit
make ci        # lint + kontrak + larangan kosakata + tes
```

Dengan `SECTORS_API_KEY` di `.env`:

```bash
make spike     # verifikasi endpoint + ukur biaya kredit aktual (maks 40 kredit)
make pipeline  # sapuan Tier-1 harian + watchlist (±5 kredit)
make backfill  # rencana tarikan historis — cetak dulu, jangan langsung jalan
```

Menyusul dari dua lajur lain: `make investigate SYMBOL=XXXX`, `make eval`.

## Cara kerja

```
sinyal pasar Tier-1 (gratis)
        ↓
   PERENCANA      → hipotesis + jalur bukti + pagu kredit
        ↓
   PENYELIDIK     → eksekusi probe → evaluasi → lanjut / dalami / berhenti
        ↓            (pagar: maks 8 langkah, 25 kredit)
   PENILAI        → skor deterministik + narasi tersitasi
        ↓
   transkrip investigasi yang bisa diputar ulang
```

Agen memutuskan **apa** yang diselidiki. Kode memutuskan **berapa** skornya.
Detail: [`ARCHITECTURE.md`](ARCHITECTURE.md) §3.
