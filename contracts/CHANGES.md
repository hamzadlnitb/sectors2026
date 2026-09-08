# contracts/CHANGES.md — sumber tunggal permintaan perubahan kontrak

Kontrak di `contracts/` dipakai tiga lajur sekaligus. Satu orang mengubahnya diam-diam =
merusak kode dua orang lain yang sudah dibangun di atasnya.

**Semua permintaan perubahan masuk ke sini. Jangan langsung edit `schemas.py`.**

---

## Cara mengajukan perubahan

1. Tambahkan entri di bagian **Diajukan** di bawah. Isi keempat kolomnya — terutama *Dampak ke lajur lain*.
2. Kabari dua orang lainnya. Perubahan disetujui kalau **ketiganya setuju**.
3. Yang mengubah kode adalah pengaju, di `contracts/`, sekalian memperbarui `fixtures/`.
4. `make check-contracts` wajib hijau sebelum push.
5. Pindahkan entrinya ke **Riwayat** dengan tanggal dan nomor commit.

Kalau ragu apakah sesuatu perlu jadi permintaan perubahan: kalau bentuknya keluar dari
`contracts/`, jawabannya ya.

## Batas beku

| Tanggal | Aturan |
| --- | --- |
| s.d. **12 Sep** | Perubahan masih murah. Ajukan bebas. |
| **setelah 12 Sep** | 🔒 **Beku.** Sesuaikan kode ke kontrak, bukan sebaliknya. Perubahan hanya untuk hal yang membuat lajur mustahil jalan — bukan untuk kerapian. |
| setelah **25 Sep** | Feature freeze. Tidak ada perubahan kontrak dalam bentuk apa pun. |

Kalau bentuknya berubah setelah ada transkrip beredar, naikkan `schema_version` supaya
fixture dan transkrip lama ketahuan basi.

---

## Diajukan

| # | Pengaju | Perubahan | Alasan | Dampak ke lajur lain | Status |
| --- | --- | --- | --- | --- | --- |
| C2 | Melco · 8 Sep, diperbarui 9 Sep | `warehouse.sql`: `free_float` PK dari `(symbol)` jadi `(symbol, as_of)` | PK `(symbol)` hanya memuat **satu** snapshot per emiten, jadi tiap tarikan baru menimpa yang lama dan riwayat free float hilang | **Hamzah:** kalibrasi menghitung sub-skor pada T-1/T-3/T-5/T-10; tanpa riwayat, FFS di tanggal itu terpaksa memakai angka hari ini — persis lookahead yang dilarang C1. Tabelnya jadi punya beberapa baris per emiten, jadi pembacaan wajib "ambil `as_of` terbesar yang ≤ tanggal acuan". **Nadhilla:** nihil, tidak membaca warehouse langsung | ⏳ menunggu persetujuan Hamzah & Nadhilla — **baca pembaruan 9 Sep dulu, alasannya bergeser** |

### C2 — rincian

**Ditemukan lewat tes, bukan review.** `tests/probes/test_point_in_time.py`
menyuntikkan data setelah `as_of` lalu membandingkan hasil probe sebelum dan
sesudah. FFS berubah `77.8 → None`: baris free float baru (bertanggal masa depan)
menimpa baris lama karena PK-nya cuma `symbol`, sehingga pada `as_of` tidak ada
baris tersisa sama sekali.

**Sementara menunggu persetujuan**, `core/ingest/warehouse.py` menggabungkan
tabel ini memakai kunci `(symbol, as_of)` lewat field `Table.merge_keys`, dengan
komentar yang menunjuk balik ke entri ini. Divergensinya sengaja dibuat terlihat
di kode, bukan disembunyikan — DDL di `contracts/` tidak disentuh.

**Kalau ditolak:** FFS harus ditandai bukan-point-in-time dan dikeluarkan dari
kalibrasi Hamzah, atau riwayat free float disimpan di tabel terpisah di luar
kontrak. Keduanya lebih mahal daripada mengubah satu baris DDL sekarang, selagi
belum ada data yang terlanjur ditulis.

#### Pembaruan 9 Sep — alasannya bergeser, bacalah ini sebelum memutuskan

Tarikan sungguhan mengubah gambarannya, dan itu harus disampaikan sebelum
ketiganya memutuskan.

**`fetch-free-float` TIDAK mengirim tanggal berlaku sama sekali.** 961 emiten
ditarik market-wide (1 kredit), seluruhnya dengan `as_of` kosong. Yang tersimpan
sekarang adalah stempel **tanggal tarikan**, bukan tanggal berlaku sebenarnya —
lihat `_stempel_as_of()` di `core/ingest/backfill.py`.

Konsekuensinya, klaim awal C2 terlalu optimistis:

* **Yang TIDAK bisa diselamatkan C2:** riwayat lampau. Sectors hanya menyediakan
  angka terkini, jadi free float pada T-10 tidak ada di mana pun dan tidak bisa
  dibackfill dengan kredit berapa pun. FFS memang belum bisa ikut kalibrasi
  historis, dengan atau tanpa C2. Ini sudah tercatat sebagai peringatan di
  `runs/backfill/pit-scores.json`, dan terlihat sebagai kolom `n/a` di sana.
* **Yang MASIH diselamatkan C2:** snapshot yang kita kumpulkan sendiri mulai
  sekarang. Dengan PK `(symbol)`, tarikan kedua menimpa yang pertama dan riwayat
  tidak pernah terbentuk — bahkan riwayat yang kita bangun dengan tangan sendiri.
  Dengan `(symbol, as_of)`, sapuan berkala menumpuk titik yang nyata dan
  bertanggal jujur.

**Jadi C2 tetap layak, tapi bukan karena alasan yang saya tulis kemarin.** Bukan
"selamatkan kalibrasi sekarang", melainkan "jangan buang riwayat yang baru mulai
dikumpulkan". Nilainya jangka menengah, bukan langsung.

**Ongkos menolaknya juga lebih rendah dari perkiraan awal**, karena FFS memang
sudah tidak bisa dikalibrasi historis. Kalau ketiganya menilai perubahan kontrak
menjelang beku 12 Sep lebih berisiko daripada manfaatnya, menolak C2 adalah
keputusan yang bisa dipertahankan — asalkan disadari bahwa FFS lalu permanen
menjadi sinyal keadaan-terkini, bukan komponen berkalibrasi, dan halaman
Metodologi harus mengatakannya.

Catatan cakupan yang sama berlaku untuk **BCI**: `fetch-broker-summary-top`
mengembalikan agregat per akhir periode tanpa rincian harian, jadi ia pun
bertanggal tanggal tarikan. Bedanya BCI tidak butuh perubahan kontrak —
`broker_summary` sudah ber-PK `(trade_date, symbol, broker_code)`. Yang ia
butuhkan adalah tarikan terpisah per tanggal acuan, dan itu soal kredit, bukan
soal bentuk data.

---

---

## Riwayat

### C1 · 8 Sep 2026 · Review kontrak v1 — 8 perbaikan

Review dilakukan terpusat supaya kontrak punya satu sumber kebenaran, bukan hasil tiga
tafsir. Semua ditemukan sebelum ada kode lajur yang dibangun di atasnya.

| # | Temuan | Kenapa ini masalah | Perbaikan |
| --- | --- | --- | --- |
| 1 | **`Probe.run(ctx: Any)` tidak bertipe** | Melco dan Hamzah akan berbeda tafsir soal apa yang diterima probe, dan baru ketahuan saat penyambungan 18 Sep | `ProbeContext` Protocol: `as_of`, `warehouse`, `client`, `budget_remaining`. Sengaja sempit supaya tidak ada jalur yang melewati ledger kredit |
| 2 | **Pagu yang dikabulkan saat eskalasi tidak tercatat** | Aritmetika kredit di `eskalasi.json` tidak nyambung (langkah 3 mestinya sisa −1, tertulis 6). Nadhilla juga tidak punya cara menampilkan *"minta tambah, dikabulkan berapa"* — padahal eskalasi salah satu dari empat perilaku yang menjual Track 1 | Field `Step.budget_granted`. `check.py` kini menelusuri pagu langkah demi langkah |
| 3 | **Logika band ditulis tiga kali** (`schemas.py`, `check.py`, `generate.py`) | Persis pola yang bikin dokumen dan kode menyimpang diam-diam | Satu fungsi `band_for_score()` di `schemas.py`; dua salinan lain dihapus |
| 4 | **`unavailable_reason` cuma imbauan di deskripsi** | Probe akan mengembalikan `sub_score=None` tanpa alasan, lalu nol yang tidak dijelaskan mencemari skor komposit tanpa ada yang sadar | `model_validator` menolak `sub_score=None` tanpa alasan, dan menolak alasan tanpa `None` |
| 5 | **`symbol` bebas** | Dokumen Sectors eksplisit: API menolak sufiks `.JK`. Cepat atau lambat ada yang mengirim `BBCA.JK` dan gagal pada saat yang salah | `pattern=^[A-Z]{4}$` |
| 6 | **`memory_ref` tanpa format** | Nadhilla tidak bisa menautkan ke investigasi sebelumnya kalau bentuknya tidak pasti | `pattern=^[A-Z]{4}-\d{4}-\d{2}-\d{2}$`, menunjuk `runs/investigations/<memory_ref>.json` |
| 7 | **`as_of` boleh datetime naif** | Data Sectors EOD dan kita wajib jujur soal keterlambatan. Datetime tanpa zona bikin tampilan WIB menyesatkan | Validator menolak datetime tanpa zona waktu |
| 8 | **Bobot kalibrasi tidak berversi** | Setelah bobot asli keluar dari H1, transkrip lama tidak bisa dibedakan dari yang pakai bobot baru | Field `weights_version`. Fixture memakai `cal-fixture`; ganti ke versi kalibrasi asli setelah H1 |

Tambahan di `check.py`: jumlah biaya langkah kini dicocokkan dengan `credits_total` dari dua
sisi (bukti dan langkah), bukan satu sisi saja.

**Diverifikasi, bukan diasumsikan.** Tiap validator diuji dengan input yang sengaja salah —
keenamnya menolak, dan penelusuran pagu menangkap eskalasi yang sisanya tidak nyambung.

Menyusul, di luar cakupan perubahan ini: `ProbeContext.as_of` mewajibkan probe bersifat
point-in-time. Melco perlu menegakkannya di tes (`tests/probes/`), karena kalibrasi Hamzah
bocor lookahead kalau ada satu probe saja yang membaca data setelah `as_of`.
