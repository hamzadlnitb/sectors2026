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

_(kosong)_

| # | Pengaju | Perubahan | Alasan | Dampak ke lajur lain | Status |
| --- | --- | --- | --- | --- | --- |

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
