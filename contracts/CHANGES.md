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
| C2 | Melco · 8 Sep | `warehouse.sql`: `free_float` PK dari `(symbol)` jadi `(symbol, as_of)` | PK `(symbol)` hanya memuat **satu** snapshot per emiten, jadi tiap tarikan baru menimpa yang lama dan riwayat free float hilang | **Hamzah:** kalibrasi menghitung sub-skor pada T-1/T-3/T-5/T-10; tanpa riwayat, FFS di tanggal itu terpaksa memakai angka hari ini — persis lookahead yang dilarang C1. Tabelnya jadi punya beberapa baris per emiten, jadi pembacaan wajib "ambil `as_of` terbesar yang ≤ tanggal acuan". **Nadhilla:** nihil, tidak membaca warehouse langsung | ⏳ menunggu persetujuan Hamzah & Nadhilla |

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

---

---

## Riwayat

### C2 · 10 Sep 2026 · Dua invarian `check.py` menolak transkrip yang sah

Ditemukan saat menulis `core/agent/` — bukan saat mereview kontrak. Keduanya
muncul dari perilaku yang kontraknya sendiri wajibkan, jadi tidak mungkin
terlihat sebelum ada agen yang benar-benar berjalan.

| # | Invarian lama | Kenapa salah | Sekarang |
| --- | --- | --- | --- |
| 1 | `ran == marked` — probe yang dijalankan harus persis sama dengan komponen terselidiki | Kontrak mewajibkan probe yang menyerah ditandai `investigated=False` (menyerah ≠ nol, `core/probes/base.py` aturan 2). Probe itu tetap punya langkah, jadi masuk `ran` tapi tidak masuk `marked` → transkrip sah ditolak. `new_probe` juga ikut dihitung, padahal ia **niat** saat eskalasi, bukan eksekusi: kalau pagar menutup loop sebelum probe barunya jalan, transkrip ditolak juga | `marked ⊆ ran`, dan `new_probe` tidak lagi dihitung. Arah yang benar-benar berbahaya cuma satu: komponen mengaku terselidiki tanpa ada langkah yang menjalankannya |
| 2 | `sum(biaya bukti) == credits_total` | Probe yang menyerah tetap membakar kredit saat fetch, tapi kontrak mengosongkan `evidence`-nya. Akibatnya biaya bukti selalu lebih kecil dari total begitu ada satu probe menyerah — dan itu kejadian biasa, bukan kasus tepi | Langkah jadi sumber kebenaran biaya: `sum(biaya langkah) == credits_total`, dan `sum(biaya bukti) <= credits_total` |

Ketiga fixture lama tetap lolos aturan baru, jadi tidak ada yang perlu
dibangkitkan ulang dan `schema_version` tetap `1.0` — bentuk datanya tidak
berubah, hanya validatornya yang diperbaiki.

**Pelajaran untuk sisa lomba:** dua-duanya lolos dari review terpusat C1 dan
baru ketahuan saat ada kode yang berjalan di atasnya. Kontrak yang belum pernah
dipakai kode sungguhan belum benar-benar tervalidasi.


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
