# PANTAU

**Sistem peringatan dini risiko manipulasi & likuiditas untuk saham IDX.**
Sectors Hackathon 2026 · Track 3 — Market Intelligence

> Untuk investor ritel IDX yang menerima rekomendasi saham dari grup Telegram dan TikTok,
> PANTAU menjawab satu pertanyaan yang tidak bisa dijawab aplikasi sekuritas mana pun:
> *"saham ini lagi ramai — ini nyata atau digoreng?"*

**PANTAU adalah alat informasi dan analisis, bukan saran investasi.**

---

## Dokumen

| File | Isi |
| --- | --- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Desain sistem, enam komponen skor, anggaran kredit, keputusan arsitektur |
| [`TASK.md`](TASK.md) | Rencana eksekusi 25 hari, peran, gerbang keputusan, rencana cadangan |
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
make pipeline  # jalankan pipeline harian (butuh SECTORS_API_KEY)
make credits   # posisi ledger kredit
make test      # unit test scoring engine
```
