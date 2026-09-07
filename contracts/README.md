# contracts/ — titik serah-terima antar lajur

Berkas di sini adalah **kesepakatan bertiga**, bukan milik satu orang.

Gunanya: Melco, Hamzah, dan Nadhilla bisa menulis kode di sisi masing-masing
tanpa menunggu siapa pun, karena bentuk data di titik serah-terima sudah pasti.

```
Melco ──ProbeResult──► Hamzah ──InvestigationTranscript──► Nadhilla
```

## Aturan

1. **Permintaan perubahan masuk ke [`CHANGES.md`](CHANGES.md), bukan langsung ke `schemas.py`.**
   Satu orang mengubah bentuk di sini = merusak kode dua orang lain yang sudah dibangun di atasnya.
2. **Beku total setelah 12 September.** Setelah itu, sesuaikan kode ke kontrak, bukan sebaliknya.
3. `schema_version` di `InvestigationTranscript` dinaikkan kalau bentuknya berubah, supaya
   fixture lama ketahuan basi.
4. Setiap perubahan wajib disertai pembaruan `fixtures/` dan lolos `make check-contracts`.

## Isi

| Berkas | Isi | Dipakai |
| --- | --- | --- |
| `schemas.py` | Lima kontrak sebagai model pydantic | ketiganya |
| `warehouse.sql` | DDL tabel DuckDB | Melco (menulis), Hamzah (membaca) |
| `check.py` | Validator: fixture harus cocok dengan skema | CI |
| `CHANGES.md` | **Sumber tunggal permintaan perubahan** + riwayat | ketiganya |

## Lima kontrak

| # | Kontrak | Serah-terima |
| --- | --- | --- |
| 1 | `ProbeResult` (+ `Probe`) | Melco → Hamzah |
| 2 | `EvidenceEntry` | Melco → Hamzah → Nadhilla |
| 3 | `InvestigationTranscript` | Hamzah → Nadhilla |
| 4 | Skema tabel warehouse | Melco → Hamzah |
| 5 | `ToolCatalogEntry` | Melco → Hamzah |
