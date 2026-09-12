# reports/agent-eval-ringkasan.md — Angka 2, kesimpulan

16 emiten, acuan 2026-09-11. Berkas mentah di `runs/evals/`, laporan per-generasi
di `reports/agent-eval*.md`. Semua generasi disimpan, termasuk yang kalah.

---

## Kesimpulan: Angka 2 tidak bisa diklaim, dan alasannya bukan agennya kalah

**Kebisingan antar-jalan sebesar seluruh selisih yang kami kejar.** Dua jalan pada
commit yang sama (`721b8a9`), data yang sama, hanya LLM yang nondeterministik:

| Metrik | v5 | v6 | Selisih |
| --- | --- | --- | --- |
| Per-emiten: agen | 75,0% | 68,8% | −6,2 pp |
| Per-emiten: urutan tetap | 75,0% | 68,8% | −6,2 pp |
| Per-emiten: acak | 68,8% | 75,0% | +6,2 pp |
| Portofolio: agen | 81,2% | 68,8% | −12,4 pp |
| Portofolio: pagu rata | 93,8% | 81,2% | −12,6 pp |

Satu emiten dari 16 bernilai **6,25 poin persentase**. Setiap selisih di tabel ini
berukuran satu sampai dua emiten — sama besar dengan goyangan yang terjadi ketika
**tidak ada yang diubah sama sekali**.

Artinya seluruh perbandingan generasi di bawah, dan seluruh usaha menaikkan agen
dari 68,8% ke 75,0%, **membaca kebisingan sebagai sinyal.** Termasuk kesimpulan
"membuka harga memperburuk" yang sempat kami tulis dan cabut.

**Konsekuensinya: klaim penghematan kredit dicabut, bukan dihaluskan.** Bukan karena
agen terbukti kalah, melainkan karena eksperimen ini tidak mampu membedakan menang
dari kalah pada ukuran sampel yang ada.

---

## Hasil bersih terakhir (commit `721b8a9`, jalan v6)

| Lengan | Per-emiten | Portofolio |
| --- | --- | --- |
| **Agen** | 6,38 kr / 68,8% | 102 kr / 68,8% |
| Urutan tetap | 6,38 kr / 68,8% | 92 kr / 81,2% |
| Acak berpagu sama | 6,19 kr / 75,0% | — |
| Oracle knapsack | — | 92 kr / 81,2% |
| Menyeluruh (acuan) | 16 kr / 100% | 256 kr / 100% |

Agen tidak mengungguli pembanding mana pun di kedua metrik, dan pada jalan ini acak
malah di atasnya. Dengan kebisingan ±6–12 pp, satu-satunya pembacaan yang jujur:
**tidak ada beda yang terdeteksi.**

---

## Yang tetap berdiri tanpa Angka 2

Pemilihan probe pada pagu tetap adalah **knapsack** — `evals/arms.himpunan_optimal()`
menyelesaikannya secara pasti lewat enumerasi 63 kombinasi, tanpa LLM. Lengan "oracle
memakai alokasi agen" menyamai agen persis di kedua jalan. Ruang itu memang tertutup;
tidak ada kecerdasan yang bisa ditunjukkan di sana, dan seharusnya kami tahu itu
sebelum mengukur, bukan sesudah.

Yang bisa diverifikasi juri tanpa bergantung pada satu angka performa:

- klien MCP tulis sendiri, satu gateway, tiap tool call termeter, ledger di-commit
- pagar agen: 8 langkah, 25 kredit, satu probe sekali, penutupan aman — tertes
- validator sitasi menolak angka **dan nama emiten** karangan — diuji dengan keluaran
  MiniMax asli yang menyebut "JAJA" untuk investigasi "JAWA"
- transkrip bisa diputar ulang: juri mengulang, hasilnya identik
- `make demo` jalan di mesin bersih tanpa API key
- eval ini sendiri, berikut catatan kegagalannya

---

## Cacat yang ditemukan lewat eval ini (semuanya sudah diperbaiki)

| Cacat | Akibatnya pada angka |
| --- | --- |
| Blok `thinking` MiniMax memakan jatah `max_tokens` sebelum `tool_use` terbit | Agen diam-diam jatuh ke keputusan if-else. Eval v1–v3 sebagian mengukur jalur cadangan, bukan agen |
| `tool_choice` yang memaksa kadang diabaikan; model menjawab teks berisi JSON | Keputusan LLM yang sebenarnya ada dibuang, diganti aturan |
| Instruksi trade-off biaya ditambahkan tanpa syarat | Lengan buta ikut menerimanya, jadi ablasi mengubah dua hal sekaligus |
| Gerbang eskalasi menolak probe yang sudah mengantre | Eskalasi mustahil menyala; nol dari 16 emiten di semua jalan |

Tiga yang pertama membuat eval v1–v4 tidak layak dikutip. Yang layak hanya v5 dan v6
— dan keduanya justru yang memperlihatkan kebisingannya.

---

## Kalau mau Angka 2 yang berarti

Bukan menyetel agen, melainkan menaikkan daya pisah eksperimennya:

1. **Perbesar sampel.** Untuk mendeteksi selisih 10 pp dengan yakin, 16 emiten jauh
   dari cukup. Prasyaratnya `broker_summary` terkini diperluas (`TASK_MELCO.md` M7).
2. **Ulangi tiap lengan beberapa kali** dan laporkan rentangnya, bukan satu angka.
   Tanpa itu, satu jalan tidak bisa dibedakan dari keberuntungan.
3. **Kurangi nondeterminisme**: `temperature` sudah 0, tapi blok thinking MiniMax
   tetap membuat keluaran bergoyang. Membandingkan penyedia bisa jadi eval tersendiri.

Sampai ketiganya ada, **Angka 2 tidak boleh muncul di video maupun README.**

---

## Batasan

- Satu tanggal acuan, 16 emiten, satu penyedia LLM.
- Lengan menyeluruh dipakai sebagai acuan band padahal ia sendiri tidak terkalibrasi
  penuh: FFS dan BCI berbobot prior domain (`contracts/CHANGES.md` C5).
- Satuan biaya adalah kredit terhitung (`cost_estimate`), bukan kredit terbakar.
  Alasannya di docstring `evals/arms.py`.
