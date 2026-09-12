# reports/agent-eval-ringkasan.md — Angka 2, kesimpulan

Ringkasan tiga generasi eval per-emiten dan satu eval portofolio, 16 emiten,
acuan 2026-09-11. Berkas mentahnya di `runs/evals/`, laporan per-generasi di
`reports/agent-eval-v1-tanpa-bobot.md`, `-v2-dengan-bobot.md`, dan `agent-eval.md`.

**Semua generasi disimpan permanen, termasuk yang kalah.** Perbandingan ini hanya
berarti kalau angka yang mempermalukan kami ikut terbaca.

---

## Kesimpulan dalam tiga kalimat

1. **Pemilihan probe pada pagu tetap: agen tidak menambah apa pun.** Solver knapsack
   yang diberi alokasi agen menghasilkan kesepakatan band yang sama persis (68,8%)
   dengan biaya sedikit lebih murah. Ruang itu memang tertutup — ada jawaban optimal
   yang bisa dihitung tanpa LLM.
2. **Alokasi pagu antar-emiten: agen menang.** 68,8% melawan 62,5% pada pagu total
   yang sama. Ini kemampuan yang knapsack tidak punya, karena knapsack harus diberi
   pagu.
3. **Membuka harga dan bobot ke perencana justru memperburuk.** Varian yang tidak
   melihat keduanya konsisten lebih baik. Klaim "pemilihan tool sadar biaya" di AD-7
   **dibantah oleh data kami sendiri** dan harus direvisi, bukan dihaluskan.

---

## Eval per-emiten — pagu sama untuk tiap emiten

| Lengan | v1 tanpa bobot | v2 dengan bobot | v3 + perbaikan eskalasi |
| --- | --- | --- | --- |
| **Agen** | 5,31 kr / **68,8%** | 6,38 kr / **68,8%** | 5,88 kr / **68,8%** |
| Urutan tetap | 5,31 kr / 81,2% | 6,38 kr / 68,8% | 5,81 kr / 68,8% |
| Acak berpagu sama | 5,00 kr / 75,0% | 6,31 kr / 68,8% | 5,62 kr / 75,0% |
| **Agen tanpa lihat harga** | 5,50 kr / 68,8% | 5,88 kr / **75,0%** | 6,19 kr / **75,0%** |
| Kepekaan harga | 93,8% | 100% | 100% |
| Eskalasi | 0 | 0 | **0** |

Agen tidak bergerak dari 68,8% di ketiga generasi. Dua intervensi — membuka bobot
komponen, lalu memperbaiki gerbang eskalasi — tidak menggeser angkanya sama sekali.

### Kenapa metrik ini tidak bisa dimenangkan

Pada pagu tetap, "pilih probe supaya cakupan bobot maksimum" adalah **knapsack**.
`evals/arms.himpunan_optimal()` menyelesaikannya secara pasti lewat enumerasi 63
kombinasi. Di pagu 5 — pagu rata-rata agen — himpunan optimalnya persis
`{broker_concentration, free_float, volume_anomaly}`, yang memang dipilih agen di
mayoritas kasus.

LLM hanya bisa menyamai atau kalah di ruang tertutup seperti itu. Metrik ini
mengukur masalah yang sudah selesai secara matematis, bukan kemampuan yang kami
klaim.

---

## Eval portofolio — satu pagu total, alokasi bebas

Pagu total **92 kredit** untuk 16 emiten. Pembanding membaginya rata (5–6 per
emiten); agen mengalokasikan sendiri.

| Lengan | Belanja | Sepakat band |
| --- | --- | --- |
| **Agen (alokasi bebas)** | 92 / 92 | **68,8%** |
| Urutan tetap, pagu rata | 80 / 92 | 62,5% |
| Oracle knapsack, pagu rata | 80 / 92 | 62,5% |
| Oracle memakai alokasi agen | 90 / 92 | **68,8%** |
| Menyeluruh (acuan) | 256 | 100% |

Sebaran alokasi agen: **1 sampai 13 kredit**, median 5. Pembagian rata memberi 5
untuk semua.

### Membaca hasilnya dengan jujur

**Yang benar-benar dimenangkan agen adalah alokasi, bukan pemilihan.** Baris
"oracle memakai alokasi agen" membuktikannya: begitu knapsack diberi alokasi yang
sama, ia menyamai agen persis (68,8%) dengan 2 kredit lebih murah. Jadi kontribusi
LLM ada di keputusan *berapa yang pantas dibelanjakan untuk emiten ini*, bukan
*probe mana yang dibeli*.

**Sebagian keunggulan itu bukan kecerdasan, melainkan granularitas.** Biaya probe
lumpy (1, 1, 2, 3, 3, 6), sehingga jatah 5–6 kredit per emiten menyisakan remah yang
tidak bisa dibelanjakan — pembagian rata hanya terpakai 80 dari 92 kredit. Alokasi
terpusat memakai pagu lebih habis. Berapa bagian dari selisih 68,8% vs 62,5% yang
berasal dari efek ini belum terpisahkan, dan **tidak boleh diklaim sebagai
kecerdasan agen** sampai terpisahkan.

---

## Tiga hal yang harus diubah di luar berkas ini

1. **AD-7 harus direvisi.** Klaim "pemilihan tool MCP yang sadar biaya" dibantah:
   perencana yang melihat harga dan bobot konsisten lebih buruk (68,8%) daripada yang
   tidak (75,0%), di dua generasi berturut-turut, dengan kepekaan harga 100% —
   artinya ia benar-benar membaca angka itu lalu memakainya untuk memutuskan lebih
   buruk. Klaim penggantinya: **alokasi pagu adaptif antar-emiten**.
2. **Eskalasi tetap nol setelah gerbangnya diperbaiki.** Perbaikan itu memang
   menghapus penghalang struktural (tertes di `tests/agent/`), tapi model tetap tidak
   pernah memilih `escalate` pada data nyata. Sampai ada bukti sebaliknya, **eskalasi
   tidak boleh ditampilkan di video sebagai perilaku yang terjadi di lapangan.**
3. **Ukuran sampel 16 emiten.** Selisih 68,8% vs 62,5% adalah 11 lawan 10 dari 16 —
   satu emiten. Itu terlalu tipis untuk disebut kemenangan tanpa kualifikasi.

---

## Batasan

- 16 emiten, satu tanggal acuan. Tidak menunjukkan kestabilan antar-waktu.
- Lengan menyeluruh dipakai sebagai acuan band padahal ia sendiri tidak terkalibrasi
  penuh: FFS dan BCI berbobot prior domain (`contracts/CHANGES.md` C5). Kesepakatan
  band mengukur konsistensi terhadap penyelidikan lengkap, **bukan** ketepatan
  terhadap kebenaran pasar.
- Satuan biaya adalah kredit terhitung (`cost_estimate`), bukan kredit terbakar.
  Alasannya di docstring `evals/arms.py`.
- Perencana LLM berhasil pada 15 dari 16 kasus; sisanya memakai rencana cadangan
  berbasis aturan dan tidak dihitung sebagai bukti kecerdasan agen.
