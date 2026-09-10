"""Bobot komposit PANTAU — konstanta, bukan logika.

Berkas ini sengaja tidak mengimpor apa pun yang berat: ia dibaca oleh penilai,
oleh agen, dan oleh laporan validasi, jadi ia harus bisa diimpor di mana saja
tanpa menyeret pandas atau DuckDB.

**Dari mana angka-angka ini berasal.** Protokolnya ada di ARCHITECTURE §6 dan
dijalankan oleh `notebooks/calibration.py`: himpunan positif = suspensi IDX yang
alasannya menyebut peningkatan harga kumulatif / cooling down, himpunan kontrol
tersamakan per subsektor dan kapitalisasi, enam sub-skor dihitung pada T-1/T-3/
T-5/T-10 hari bursa sebelum peristiwa, strictly point-in-time.

Per 10 September 2026 protokol itu **belum bisa menghasilkan bobot**: warehouse
yang di-commit hanya memuat riwayat harga untuk 16 emiten dan seluruh peristiwa
positif yang bisa dinilai jatuh di rentang Agustus–September 2026, sehingga
split waktu 18 bulan / 6 bulan tidak punya bahan. Jalankan
`python3 notebooks/calibration.py` untuk melihat hitungan sampel terkini dan
`reports/validation.md` untuk daftar persis data yang kurang.

Karena itu bobot di bawah adalah **prior domain yang bisa dipertahankan**, bukan
hasil regresi. Setiap angka punya alasan yang bisa diucapkan dalam 15 detik:

  BCI 0,25 — bukti paling langsung untuk "segelintir pihak yang mengumpulkan".
             Konsentrasi net buy 3 broker adalah satu-satunya komponen yang
             berbicara tentang PELAKU, bukan tentang jejaknya. Bobot tertinggi.
  VAS 0,22 — lonjakan volume adalah sinyal paling awal dan paling universal;
             hampir selalu tersedia, jadi ia yang paling sering menentukan
             apakah sebuah emiten masuk radar sama sekali.
  FFS 0,18 — free float kecil adalah PRASYARAT struktural: makin sedikit saham
             beredar, makin murah harga digerakkan. Bukan bukti, tapi pengali
             kredibilitas untuk semua sinyal lain.
  FRD 0,15 — asing keluar sementara harga naik adalah pola distribusi ke ritel.
             Kuat kalau ada, tapi banyak emiten lapis ketiga nyaris tidak punya
             arus asing sehingga komponen ini sering kosong.
  PFD 0,12 — divergensi harga vs laba bergerak lambat (laporan kuartalan) dan
             lebih sering MENGONFIRMASI daripada MENDAHULUI peristiwa.
  SSS 0,08 — riwayat suspensi/insider/rights issue adalah konteks korporasi.
             Sengaja paling kecil: label kita SENDIRI berasal dari suspensi,
             jadi memberinya bobot besar akan membuat validasi memuji dirinya
             sendiri.

Jumlahnya tepat 1,0. Diuji di notebooks/calibration.py.
"""

from __future__ import annotations

WEIGHTS: dict[str, float] = {
    "BCI": 0.25,
    "VAS": 0.22,
    "PFD": 0.12,
    "FFS": 0.18,
    "FRD": 0.15,
    "SSS": 0.08,
}

# Sufiks "-sementara" WAJIB bertahan sampai kalibrasi benar-benar berjalan atas
# sampel yang cukup. Transkrip investigasi menyimpan versi ini apa adanya, jadi
# siapa pun yang membaca runs/ nanti bisa tahu bobot mana yang belum teruji.
WEIGHTS_VERSION: str = "cal-2026-09-10-sementara"

# Ambang minimum sebelum bobot boleh diganti hasil regresi. Angka ini bukan
# selera: di bawah ~30 positif, satu peristiwa saja menggeser bobot komponen
# lebih dari 0,05 dan "kalibrasi" jadi nama lain untuk overfitting.
MIN_POSITIF_UNTUK_KALIBRASI: int = 30
