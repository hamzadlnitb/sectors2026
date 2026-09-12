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

_(kosong — tidak ada permintaan perubahan yang menggantung)_

---

## Riwayat

### C5 · 12 Sep 2026 · Tanggapan Hamzah atas C4, dan batas kalibrasi yang sebenarnya

**C4 diterima.** Ongkosnya nol, dan alasan revisi 10 Sep lebih jujur daripada yang
8 Sep: ini bukan penyelamat kalibrasi, melainkan penjaga riwayat yang baru mulai
dikumpulkan. Dengan PK `(symbol)`, tarikan kedua menimpa yang pertama dan riwayat
tidak pernah terbentuk — bahkan riwayat yang kita bangun sendiri. Itu argumen yang
berdiri sendiri. Tidak ada pembatalan yang diajukan.

Soal caranya: keputusan sepihak menjelang beku, dicatat terbuka, dengan jalan
pulang satu baris DDL. Itu penanganan yang benar untuk perubahan berongkos nol,
dan mencatatnya apa adanya lebih berharga daripada persetujuan formal yang
terlambat.

#### Konsekuensi yang lebih besar daripada C4 itu sendiri

Temuan Melco — `fetch-free-float` tidak mengirim tanggal berlaku — gua verifikasi
langsung dengan menjalankan probe pada dua tanggal acuan:

| Probe | `as_of` 2026-08-20 | `as_of` 2026-09-11 |
| --- | --- | --- |
| `free_float` | n/a | 94 |
| `broker_concentration` | n/a | 38 |
| `volume_anomaly` | 100 | 16 |

Saringan point-in-time bekerja persis seperti seharusnya, dan justru itu yang
memperlihatkan batasnya: **FFS dan BCI tidak bisa dihitung pada tanggal lampau,
jadi keduanya tidak bisa ikut kalibrasi historis.** Untuk FFS ini permanen —
Sectors hanya menyediakan angka terkini, dan tidak ada jumlah kredit yang bisa
membelinya. Untuk BCI ini soal kredit, tapi dengan hanya 18 emiten tersuspend yang
punya riwayat harga, kalibrasinya tetap di bawah ambang 30 positif.

**Keputusan, sebagai pemilik lajur kalibrasi:** berhenti mengejar kalibrasi
historis untuk FFS dan BCI. Bobot keduanya (0,18 + 0,25 = **0,43 dari total**)
tetap prior domain, dinyatakan terbuka di halaman Metodologi dan di
`reports/validation.md`. Angka 1 dilaporkan apa adanya sebagai terkalibrasi atas
**empat dari enam komponen**. Melebih-lebihkannya akan ditangkap juri praktisi
pasar dalam sedetik; mengakuinya duluan justru menambah kredibilitas. `[T7]`

#### Yang TIDAK terhambat — dan ini membalik prioritas

Angka 2 (efisiensi perutean agen) berjalan pada `as_of` terkini, bukan lampau.
Pada tanggal terkini **keenam probe hidup**, seperti terlihat di kolom kanan tabel
di atas. Jadi:

* **H3 eval agen TIDAK terhambat backfill historis.** Bisa dimulai sekarang.
* Angka 2 tidak bergantung pada bobot terkalibrasi: ia mengukur kesepakatan band
  antar-lengan eval, dan seluruh lengan memakai bobot yang sama.
* Yang dibutuhkan hanya **keluasan** `broker_summary` pada tanggal terkini: kini
  16 emiten, sementara 39 emiten punya riwayat harga. Menutup selisihnya ±23
  panggilan × 2 kredit = **±46 kredit**.

**Akibatnya M7 di `TASK_MELCO.md` — tarikan 24 bulan yang gua minta 10 Sep —
sebagian besar sia-sia dan gua koreksi sendiri.** Yang berharga tinggal perluasan
`daily_transaction` (sudah dikerjakan: 16 → 39 emiten) dan `broker_summary`
terkini yang murah itu. Menarik 24 bulan riwayat broker tidak akan mengangkat
kalibrasi melewati ambang, dan tidak dibutuhkan Angka 2.


### C4 · 10 Sep 2026 · `free_float` PK jadi `(symbol, as_of)` — DISETUJUI

**Cara persetujuannya, supaya tercatat apa adanya:** Melco memutuskan dan
menyatakan menanggung tanggung jawabnya, bukan lewat konsensus bertiga seperti
yang diminta aturan di kepala berkas ini. Hamzah dan Nadhilla belum sempat
menanggapi menjelang beku 12 Sep. Dicatat terbuka karena aturan yang dilanggar
diam-diam lebih buruk daripada aturan yang dilanggar sadar — dan karena
perubahan ini menyentuh berkas milik bersama.

Ongkos kalau keputusan ini keliru rendah: nol perubahan perilaku, 315 tes tetap
hijau, dan mengembalikannya cukup satu baris DDL selama belum ada riwayat yang
terlanjur terkumpul. Kalau salah satu dari mereka keberatan, ajukan pembatalan
sebagai entri baru — jangan sunting entri ini.

**Yang berubah:** `PRIMARY KEY (symbol)` → `PRIMARY KEY (symbol, as_of)`,
keduanya `NOT NULL`. `Table.merge_keys` di `core/ingest/warehouse.py` tidak lagi
menyimpang dari kontrak; penyimpangan sementaranya dihapus.

**Pembacaan wajib** "ambil `as_of` terbesar yang ≤ tanggal acuan" — ditegakkan
view di `connect()`, bukan diserahkan ke pemanggil.

`schema_version` tetap `1.0`: bentuk data yang menyeberang antar lajur
(`ProbeResult`, `EvidenceEntry`, `InvestigationTranscript`) tidak berubah sama
sekali. Yang berubah hanya kunci tabel internal warehouse.

#### Alasan asli (diajukan 8 Sep) dan koreksinya

> **Dulu bernomor C2.** Dinomori ulang 10 Sep karena Hamzah memakai C2 dan C3
> untuk perbaikan `check.py` dan validator narasi, dan keduanya sudah masuk
> Riwayat serta dirujuk kode yang sudah merge. Sempat ada tujuh rujukan "C2" di
> repo yang menunjuk **dua hal berbeda** — persis kekacauan yang berkas ini ada
> untuk mencegahnya. Yang pindah adalah entri yang masih menggantung, karena itu
> yang paling murah. Nomor tidak pernah dipakai ulang.

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
kontrak.

#### Pembaruan 10 Sep — alasannya bergeser, baca ini sebelum memutuskan

Tarikan sungguhan mengubah gambarannya, dan itu harus disampaikan sebelum
ketiganya memutuskan.

**`fetch-free-float` TIDAK mengirim tanggal berlaku sama sekali.** 961 emiten
ditarik market-wide (1 kredit), seluruhnya dengan `as_of` kosong. Yang tersimpan
adalah stempel **tanggal tarikan**, bukan tanggal berlaku sebenarnya — lihat
`_stempel_as_of()` di `core/ingest/backfill.py`.

Konsekuensinya klaim awal saya terlalu optimistis:

* **Yang TIDAK diselamatkan perubahan ini:** riwayat lampau. Sectors hanya
  menyediakan angka terkini, jadi free float pada T-10 tidak ada di mana pun dan
  tidak bisa dibackfill dengan kredit berapa pun. FFS memang belum bisa ikut
  kalibrasi historis, dengan atau tanpa C4. Sudah tercatat sebagai peringatan di
  `runs/backfill/pit-scores.json`, terlihat sebagai kolom `n/a` di sana.
* **Yang MASIH diselamatkan:** snapshot yang kita kumpulkan sendiri mulai
  sekarang. Dengan PK `(symbol)`, tarikan kedua menimpa yang pertama dan riwayat
  tidak pernah terbentuk — bahkan riwayat yang kita bangun dengan tangan sendiri.

**Jadi C4 tetap layak, tapi bukan karena alasan yang saya tulis 8 Sep.** Bukan
"selamatkan kalibrasi sekarang", melainkan "jangan buang riwayat yang baru mulai
dikumpulkan". Nilainya jangka menengah, bukan langsung.

**Ongkos menolaknya juga lebih rendah dari perkiraan awal**, karena FFS memang
sudah tidak bisa dikalibrasi historis. Menolak C4 adalah keputusan yang bisa
dipertahankan — asalkan disadari FFS lalu permanen jadi sinyal keadaan-terkini,
bukan komponen berkalibrasi, dan halaman Metodologi mengatakannya.

Catatan cakupan serupa untuk **BCI**: `fetch-broker-summary-top` mengembalikan
agregat per akhir periode tanpa rincian harian, jadi ia pun bertanggal tanggal
tarikan. Bedanya BCI **tidak butuh perubahan kontrak** — `broker_summary` sudah
ber-PK `(trade_date, symbol, broker_code)`. Yang ia butuhkan tarikan terpisah per
tanggal acuan: soal kredit, bukan soal bentuk data.

---


### C3 · 10 Sep 2026 · Validator narasi tidak pernah memeriksa nama emiten

Ditemukan pada uji end-to-end pertama lawan MiniMax M3. Narasi yang dihasilkan
**lolos validator angka sepenuhnya** — setiap angkanya bersumber dari buku bukti —
tetapi berbunyi *"Investigasi pada saham JAJA…"* untuk investigasi emiten **JAWA**.

Validator hanya membaca angka, karena itulah yang C1 rancang. Tapi menyebut emiten
yang salah lebih berbahaya daripada angka yang salah: angka yang meleset membuat
pembaca salah menilai satu saham, sedangkan nama yang meleset membuatnya bertindak
di saham yang sama sekali lain. Dan juri praktisi pasar akan menangkapnya dalam
sedetik.

Ditambahkan `core/narrative/validate.py::unsupported_tickers()`: setiap token empat
huruf kapital di narasi yang bukan emiten yang sedang diselidiki diperlakukan sebagai
halusinasi, kecuali segelintir singkatan pasar modal yang didaftar eksplisit
(`RUPS`, `IUPK`, …). Menambah entri ke daftar itu melemahkan pemeriksaan, jadi
tambahkan hanya kalau istilahnya benar-benar muncul dan benar-benar sah.

`narrate()` kini jatuh ke template deterministik kalau pemeriksaan ini gagal, sama
seperti pada angka tak bersumber. Tes memakai keluaran MiniMax aslinya, bukan contoh
karangan: `tests/narrative/test_ticker.py::test_emiten_karangan_tertangkap`.

Tidak ada perubahan bentuk data — `schema_version` tetap `1.0`.

**Pelajaran, menguatkan C2:** validator hanya memeriksa apa yang terpikir saat
menulisnya. Yang menemukan celah ini bukan review, melainkan satu panggilan sungguhan
ke model sungguhan.


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
