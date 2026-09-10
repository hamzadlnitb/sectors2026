# reports/validation.md — Angka 1

> Dihasilkan `python3 notebooks/calibration.py --tulis` pada 2026-09-10.
> Jangan diedit tangan: tiap angka di bawah keluar dari skrip itu, atas
> `data/warehouse/` yang di-commit, **nol panggilan jaringan**.

Bobot yang berlaku: `cal-2026-09-10-sementara` — BCI 0,25, VAS 0,22, PFD 0,12, FFS 0,18, FRD 0,15, SSS 0,08.

---

## Ringkasan satu paragraf

Protokol §6 dijalankan penuh dan **belum menghasilkan bobot terkalibrasi.**
Dari 536 baris suspensi (280 emiten) di warehouse,
452 beralasan pergerakan harga — digabung jadi
**348 episode**. Yang benar-benar **bisa dinilai** hanya
**9**, karena riwayat harga di warehouse cuma mencakup
16 emiten dengan >= 40 sesi. Kontrol tersamakan
yang terbentuk: **27**. Bobot di `core/scoring/weights.py` karena itu
adalah **prior domain**, ditandai `-sementara`, bukan hasil regresi.

## Angka 1

| Metrik | Seluruh sampel | Bagian uji (lebih baru) |
| --- | --- | --- |
| Pengamatan (emiten x peristiwa) | 31 | 19 |
| Positif / kontrol | 9 / 22 | 6 / 13 |
| Precision@20 | 0,45 | 0,32 |
| Recall pada ambang >= 60 | 0,33 | 0,33 |
| Median lead time (hari bursa) | 5,0 | 7,5 |
| Keyakinan rata-rata (bobot terisi) | 0,56 | 0,57 |

Precision@20 di sini **bukan** Precision@20 yang sesungguhnya: seluruh semesta
cuma 31 pengamatan berskor (k = 20), jadi 20 teratas
hampir sama dengan seluruh daftar dan angkanya mendekati proporsi positif di
sampel. Pada himpunan sekecil ini satu emiten memindahkan angka lebih dari 0,1 —
perlakukan kolom di atas sebagai bukti bahwa pipa perhitungannya jalan, bukan
sebagai klaim performa.

## Daya pisah per komponen

AUC = seberapa sering komponen memberi nilai lebih tinggi pada saham yang
benar-benar disuspensi daripada pada kembarannya yang tidak. 0,5 = tidak
memisahkan sama sekali.

| Komponen | AUC | Sub-skor terisi |
| --- | --- | --- |
| BCI | belum bisa dihitung | 0 |
| VAS | 0,85 | 144 |
| PFD | 0,80 | 136 |
| FFS | belum bisa dihitung | 0 |
| FRD | 0,53 | 144 |
| SSS | 0,89 | 144 |

Kolom terakhir adalah masalah sebenarnya: komponen yang jarang terisi tidak bisa
dikalibrasi, seberapa pun bagus rumusnya.

## Protokol yang dijalankan

1. **Positif** — kolom `reason` di `suspensions.parquet` dibaca apa adanya. Dua
   bentuk kalimat yang ada di data: "Terjadinya peningkatan harga kumulatif yang
   signifikan pada saham XXXX.JK" dan tambahan "dalam rangka cooling down
   sebagai bentuk perlindungan bagi investor". Alasan administratif (laporan
   keuangan telat, biaya pencatatan, papan pemantauan khusus) **dikeluarkan**.
   Suspensi berulang pada emiten sama dalam 10 hari dihitung
   satu episode.
2. **Kontrol** — 3 emiten per positif, **tanggal sama**,
   disamakan subsektor lalu kedekatan log-kapitalisasi dari `company_profile`.
3. **Point-in-time** — sub-skor dihitung lewat `Context(as_of=T-k)`;
   `Warehouse.connect` menyaring tiap view ke `<= as_of`, jadi tanggal suspensi
   memang tidak ada di sesi itu. Nol lookahead ditegakkan struktur.
4. **Nol jaringan** — `Context(client=None)`; `Context.ensure()` pulang membawa
   nol tanpa menyentuh `CreditAwareClient`.
5. **Bobot** — alokasi sebanding (AUC - 0,5), dinormalkan ke 1,0. Dipilih karena
   bisa dijelaskan dalam 15 detik. **Tidak dijalankan** selama positif yang bisa
   dinilai < 30.
6. **Split waktu** — batas = persentil 75 dari **tanggal peristiwa unik**:
   48 baris pengamatan masuk kalibrasi, 96 masuk uji.
   Pembagiannya timpang karena tanggal uniknya cuma segelintir; lihat Batasan 3.

---

# BATASAN

**Yang di bawah ini bukan basa-basi. Baca sebelum memakai angka mana pun.**

**1. Bobotnya belum terkalibrasi.** `WEIGHTS_VERSION` sengaja berakhiran
`-sementara`. Angkanya adalah prior domain yang alasannya ditulis satu per satu
di `core/scoring/weights.py`, bukan keluaran regresi. Siapa pun yang mengutip
"bobot terkalibrasi" dari repo ini per hari ini salah kutip.

**2. Sampelnya terlalu kecil, dan inilah angkanya.** 9
positif yang bisa dinilai, 27 kontrol. Ambang yang kami tetapkan
sebelum melihat hasil adalah **30 positif**; di bawah
itu satu peristiwa menggeser bobot komponen lebih dari 0,05.

**3. Split waktu tidak berarti.** Seluruh peristiwa yang bisa dinilai jatuh di
rentang 2026-08-11 .. 2026-09-04 — hitungan pekan, bukan 18 bulan + 6 bulan seperti yang
diminta §6. "Bagian uji" di tabel Angka 1 berasal dari pekan yang sama dengan
bagian kalibrasi, jadi ia **tidak membuktikan generalisasi apa pun**.

**4. Suspensi bukan sinonim manipulasi.** IDX menyuspensi karena kenaikan
kumulatif yang signifikan; sebagian episode itu berita korporasi yang sah.
Sebaliknya, manipulasi yang berhasil justru tidak memicu suspensi. Label kita
adalah proksi, dan proksi yang bias ke arah yang mudah terlihat.

**5. SSS berpotensi melihat jawabannya sendiri.** Komponen SSS membaca riwayat
suspensi, dan label kita juga berasal dari suspensi. Point-in-time mencegah ia
membaca peristiwa yang sedang dinilai, tapi emiten yang pernah disuspensi
memang lebih mungkin disuspensi lagi. Itu sebabnya SSS diberi bobot terkecil
(0,08), dan sebabnya angka AUC SSS tidak boleh dibaca sebagai daya prediksi.

**6. Kontrol tidak benar-benar tersamakan.** `company_profile` hanya memuat
16 baris, jadi untuk sebagian besar positif tidak ada pasangan
sesubsektor dan penyamaan turun ke kapitalisasi saja — atau gagal sama sekali.

**7. BCI dan FFS — 0,43 dari total bobot — TIDAK PERNAH terisi dalam kalibrasi
ini.** `broker_summary` dan `free_float` masing-masing cuma punya satu tanggal
di warehouse, dan tanggal itu jatuh SESUDAH sebagian besar T-k. Setelah saringan
point-in-time keduanya kosong. Konsekuensinya keras: angka Angka 1 di atas
sesungguhnya berasal dari VAS + PFD + FRD + SSS saja, dan komponen yang kami
beri bobot TERBESAR justru komponen yang belum pernah diuji sekali pun.

**8. Komponen kosong menurunkan keyakinan, tidak menaikkan skor.** Itu perilaku
yang benar (§4) dan bukan bug — tapi artinya Skor PANTAU hari ini praktis
ditentukan dua sampai tiga komponen, dengan keyakinan rata-rata
0,56.

---

# YANG DIBUTUHKAN SUPAYA ANGKA INI JADI NYATA

Urut menurut pengaruh per kredit:

| Kebutuhan | Sekarang | Target | Kenapa |
| --- | --- | --- | --- |
| Riwayat `daily_transaction` | 16 emiten >= 40 sesi | >= 150 emiten x 120 sesi | Penentu tunggal berapa positif yang bisa dinilai. Tanpa ini yang lain tidak berguna. |
| Rentang tanggal riwayat harga | beberapa bulan | 24 bulan penuh | Split waktu 18/6 bulan mustahil tanpa ini. |
| `company_profile` | 16 baris | seluruh emiten kandidat | Kontrol tersamakan butuh subsektor + kapitalisasi. |
| `broker_summary` | 16 emiten, 1 tanggal | 20 sesi x tiap kandidat | BCI berbobot terbesar tapi **tidak pernah terisi** pada T-k mana pun. |
| `foreign_flow` | 16 emiten, 62 tanggal | seluruh kandidat | FRD terisi tapi AUC-nya ~0,5 — belum ada daya pisah. |
| Riwayat `free_float` | 961 emiten, 1 tanggal snapshot | snapshot bulanan | Satu tanggal snapshot berarti FFS pada T-k **kosong** setelah saringan point-in-time. |

Perkiraan kasar: **>= 30 episode positif yang bisa
dinilai** dengan rentang peristiwa **>= 12 bulan**. Dengan tingkat suspensi yang
terlihat di 24 bulan terakhir (348 episode di
280 emiten), itu berarti backfill `daily_transaction` untuk
sekitar 150 emiten paling aktif — bukan seluruh papan.

---

PANTAU adalah alat informasi dan analisis, bukan saran investasi.
