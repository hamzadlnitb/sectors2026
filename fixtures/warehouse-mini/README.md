# fixtures/warehouse-mini/ — warehouse mini untuk tes tanpa jaringan

> ⚠️ **Seluruh angka di direktori ini karangan.** Ticker `FIXA`–`FIXF` fiktif.
> Tidak boleh dipakai untuk klaim apa pun tentang emiten sungguhan, dan tidak
> boleh tercampur dengan `data/warehouse/` yang berisi tarikan Sectors asli.

**Pemilik: Melco** (pengecualian eksplisit di `TASK.md` §Kontrak & fixture —
sisa `fixtures/` milik Nadhilla). Enam probe di `core/probes/` diuji di atas
berkas ini setiap kali CI jalan, tanpa API key dan tanpa jaringan.

## Bangkitkan ulang

```bash
make warehouse-mini
```

Seed tetap (`20260905`), jadi keluarannya identik tiap kali. Parquet-nya
di-commit supaya `git clone` → `make test` langsung hijau.

## Enam ticker, enam bentuk masalah

| Ticker | Cerita | Yang diuji |
| --- | --- | --- |
| `FIXA` | Tenang, kapitalisasi besar, float 62% | Semua komponen keluar rendah — probe tidak boleh "menemukan" pola yang tidak ada |
| `FIXB` | Harga +142%/90 hari, laba −8%, 3 broker kuasai net buy, volume 4,4σ, 3 filing jual insider | Jalur waspada penuh |
| `FIXC` | Free float 4%, volume 5,5σ, 2 rights issue, pernah disuspend Nov 2025 | Jalur sangat waspada + eskalasi |
| `FIXD` | IPO 20 Agu 2026, riwayat 12 hari bursa | Probe wajib bilang "data kurang", **bukan** crash dan **bukan** skor nol diam-diam |
| `FIXE` | Disuspend sejak 1 Sep 2026, data berhenti 31 Agu | Ticker tersuspend tidak menjatuhkan probe |
| `FIXF` | Ada di `daily_close`, tidak ada di tabel lain | Data hilang → `sub_score=None` + `unavailable_reason` |

## Umpan lookahead

Tabel pasar memuat baris **setelah** `as_of` (2026-09-08 dan 2026-09-09).
Baris itu tidak boleh terlihat probe mana pun: `Warehouse.connect(as_of)`
memasang view yang sudah tersaring. `tests/probes/test_point_in_time.py`
membuktikannya dengan membandingkan hasil probe pada `as_of` yang sama sebelum
dan sesudah data masa depan ditambah.

Kenapa ini penting: satu probe yang membaca data setelah `as_of` membocorkan
lookahead ke kalibrasi bobot Hamzah, dan Angka 1 di `reports/validation.md`
jadi bohong tanpa ada yang sadar. `contracts/CHANGES.md` C1, catatan penutup.

## Catatan tanggal

`as_of = 2026-09-05` (sama dengan `fixtures/transcripts/`) jatuh pada **Sabtu**.
Hari bursa terakhir yang terlihat karena itu **Jumat 2026-09-04**. Ini disengaja:
probe tidak boleh mengasumsikan `as_of` selalu hari bursa.
