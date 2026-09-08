# data/warehouse/ — snapshot Sectors yang di-commit

Parquet di direktori ini **di-commit ke repo**, dan itu disengaja: juri
melakukan `git clone` lalu `make demo`, dan seluruh sistem jalan tanpa
kredensial apa pun. `ARCHITECTURE.md` AD-2.

Isinya data Sectors **asli**, bukan fixture. Yang sintetis ada di
`fixtures/warehouse-mini/` dan tidak boleh tercampur ke sini.

Skema tabel: `contracts/warehouse.sql` (beku, kesepakatan bertiga).
Ditulis: `core/ingest/tier1_market.py` (harian) dan `core/ingest/backfill.py`
(historis). Dibaca point-in-time lewat `core/ingest/warehouse.py`.

**Masih kosong** — menunggu `SECTORS_API_KEY`. Sampai terisi, `make demo`
otomatis jatuh ke `fixtures/warehouse-mini/` dan mengatakannya di layar.
