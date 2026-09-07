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

🚧 Perencanaan. Belum ada kode. Lihat `TASK.md` fase F0.

## Quickstart (target — berlaku setelah F3)

```bash
git clone <repo> && cd pantau
make demo      # jalan penuh dari snapshot yang di-commit, TANPA API key
```

```bash
make investigate SYMBOL=BBCA   # jalankan agen sungguhan (butuh SECTORS_API_KEY)
make eval                      # agen vs menyeluruh vs urutan tetap vs acak
make pipeline                  # pipeline harian
make credits                   # posisi ledger kredit
make test                      # unit test probe, pagar agen, validator sitasi
```

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
