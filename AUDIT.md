# AUDIT.md — Audit kode PANTAU: bug terkonfirmasi, lubang desain agen, terobosan

**23 September 2026. 5 hari bursa tersisa (23, 24, 25, 28, 29 Sep). Feature freeze 25 Sep.**
Lingkup: kode saja. Video, user testing, dan copywriting README sengaja di luar dokumen ini.

Setiap temuan di §1 **direproduksi**, bukan dibaca. Setiap usulan di §3 menyebut berkas, pemilik
lajur, perkiraan ukuran, dan tes yang harus menyertainya. Kontrak di `contracts/` **tidak
disentuh** oleh satu pun usulan — semuanya di dalam batas beku 12 Sep.

---

## 0. Ringkasan

| Kelas | Jumlah | Yang paling berbahaya |
| --- | --- | --- |
| Bug terkonfirmasi (reproduksi + patch) | 9 | Timeout pagar agen **tidak bekerja** — cron bisa menggantung; watchlist mengurutkan kandidat dengan fungsi yang **tidak monoton** |
| Lubang desain agen (membuat agen kurang "agentik" dari yang diklaim) | 9 | Penyelidik memutuskan `conclude` **hanya melihat probe terakhir**, tanpa bukti langkah sebelumnya |
| Terobosan (diranking dampak ÷ usaha) | 10 | Konteks bukti berjalan + gerbang keyakinan minimum; jalur permintaan via Issue; ganti penyedia LLM produksi |

Prioritas mutlak hari ini, sebelum cron 17:30 WIB: **merge `fix/hamzah/probe-data-basi` ke `main`**
(§1 B8). Tanpa itu investigasi malam ini kembali 0 kredit dan watchlist tetap beku.

---

## 0.1 Status pelaksanaan — diperbarui 24 September 2026

Ditulis oleh Hamzah setelah mengeksekusi audit ini. Tanda di tiap judul §1/§2:
**✅ selesai** (kode + tes + di `main`), **⏸ tertunda** (terhalang di luar kode),
**🟨 separuh**, **⬜ belum**.

| Kelas | Selesai | Sisa |
| --- | --- | --- |
| Bug §1 | B1, B7, B8, B9 + N1 | B2, B3, B4, B6 · B5 separuh |
| Lubang desain §2 | D1, D2, D3, D4, D6, D7 | D5, D8 · D9 tertunda (kontrak beku) |
| Terobosan §3 | T1, T2, T6 | T3, T5, T7, T8, T9, T10 · T4 tertunda (secret) |

**Sudah di `main`:**

| Commit | Isi |
| --- | --- |
| `3e667be` | **Akar masalah** — `ensure()` menilai kecukupan dari jumlah baris, bukan kesegaran; `runner.py` mengarang fase kredit `"agent"` yang tidak ada di `CAPS` |
| `6e6e65a` | `Step.reason` dari LLM lolos gerbang larangan kosakata [K5] |
| `161ff4f` | 21 investigasi backfill 10–21 Sep + pulihkan sapuan 21 Sep dari artefak |
| `b6cbfb1` | B1 — timeout pagar probe + tiga tes |
| `eb4b04a` | **T1** — D1, D2, D6, D7, B7 |
| `4e63f49` | **T2** — D3, D4, B9 |
| `965db91`, `51eae05` | Melco, tindak lanjut review PR #16 — N1 + lubang `daily_transaction` |

Gerbang: `make ci` hijau seluruhnya — ruff bersih, `check-contracts` lolos, larangan
kosakata bersih atas 125 berkas, **365 tes lulus**. Nol perubahan di `contracts/`.

### Temuan baru di luar audit ini

**N1 · `daily.yml` tidak mengunggah `runs/investigations/`** ✅ *(ditutup `965db91`)*
Run cron `35626248508` (21 Sep) gagal di langkah commit. Sapuan `runs/2026-09-21/` bisa
dipulihkan karena langkah unggah artefak memakai `if: always()` — tapi investigasinya
**hilang permanen**, karena langkah itu hanya mencakup `runs/<date>/`. Tiga emiten hari
itu harus dijalankan ulang dengan kredit baru.

**N2 · Skor berbanding TERBALIK dengan kedalaman investigasi** ⬜ *(struktural)*
Terlihat jelas begitu riwayat ditampilkan di dashboard: ASLI 11 Sep = skor **100** dari
**1/6** komponen (keyakinan 0,22); ASLI 14 Sep = skor **47** dari **4/6** (keyakinan
0,80). `composite.score` merenormalisasi atas komponen yang TERSEDIA, jadi makin sedikit
yang diperiksa makin ekstrem hasilnya. D2 (pagar #5) memotong kasus terburuknya dan UI
kini menampilkan `n/6 komponen`, tapi akar strukturalnya — band ditulis tanpa
memperhitungkan cakupan — masih ada. Kandidat perbaikan pasca-freeze: band di-*clamp*
oleh keyakinan, atau bobot komponen yang absen dihitung sebagai netral, bukan dibuang.
Keduanya menyentuh `contracts/` (`band`), jadi lewat CHANGES.

---

## 1. Bug terkonfirmasi

### B1 · Timeout pagar agen dekoratif — `core/agent/guardrails.py` (Hamzah) 🔴 ✅
**Reproduksi:** probe yang `sleep(3)` dengan `Guardrails(timeout=0.5)` → `run_probe` kembali
setelah **3,01 detik**, bukan 0,5. Alasan: `with ThreadPoolExecutor(...) as pool:` — `__exit__`
memanggil `shutdown(wait=True)` dan **menunggu thread selesai**, membatalkan
`pool.shutdown(wait=False, cancel_futures=True)` yang dipanggil di dalamnya. Pagar #2 di docstring
("satu probe yang menggantung tidak boleh menyandera cron") tidak pernah ditegakkan. Tidak ada tes
timeout di `tests/agent/`.
Bonus kosmetik: pesan `f"timeout {self.timeout:.0f} detik"` mencetak "0 detik" untuk 0,5.

**Patch:**
```python
pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"probe-{name}")
future = pool.submit(probe.run, symbol, ctx)
try:
    hasil = future.result(timeout=self.timeout)
except FutureTimeout:
    self._breach(f"probe '{name}' melewati timeout {self.timeout:g} detik")
    pool.shutdown(wait=False, cancel_futures=True)   # JANGAN pakai with
    return ProbeResult(probe=name, sub_score=None, credits_spent=0,
                       unavailable_reason=f"probe melewati timeout {self.timeout:g} detik")
except Exception as exc: ...
finally-not-needed: pool.shutdown(wait=False)
```
Thread yang tertinggal dibiarkan mati sendiri (proses berumur satu investigasi, sesuai komentar
yang sudah ada). **Tes:** `test_timeout_mengembalikan_sebelum_probe_selesai` — probe `sleep(2)`,
timeout 0,2, assert durasi < 1 detik dan `sub_score is None`.

### B2 · Normalisasi sinyal watchlist tidak monoton — `core/ingest/tier1_market.py::_clip` (Melco) 🔴 ⬜
```
_clip(1.4) = 1.00   _clip(1.5) = 1.00   _clip(1.6) = 0.267   _clip(3.0) = 0.50
```
`value / 6.0 if value > 1.5 else value` → z-score **1,5σ dinilai lebih tinggi daripada 3σ**.
Ini fungsi yang menentukan tiga emiten mana yang diselidiki agen tiap hari (bobot `volume_z` 40%).
Ranking watchlist selama ini sebagian acak.

**Patch:** normalisasi per sinyal, bukan satu `_clip` untuk semua:
```python
NORMALISASI = {
    "volume_z":  lambda v: max(0.0, min(1.0, v / 6.0)),     # 6σ = penuh, selaras VAS
    "return_5d": lambda v: max(0.0, min(1.0, v / 0.30)),    # +30% dalam 5 hari = penuh
    "return_20d":lambda v: max(0.0, min(1.0, v / 0.60)),
    "small_cap": lambda v: v,
    "peristiwa": lambda v: v,
}
skor = sum(BOBOT[k] * (NORMALISASI[k](v) if v is not None else 0.0) for k, v in sinyal.items())
```
**Tes:** monotonik — untuk tiap sinyal, `f(a) <= f(b)` bila `a < b`.

### B3 · `return_5d` dihitung atas baris yang tidak berurutan — `tier1_market.py::screen` (Melco) 🟠 ⬜
Universe watchlist = 130 emiten, **median 2 baris harga per emiten** (hanya 39 yang punya riwayat
backfill; sisanya muncul sesekali di most-traded/top-changes). `_pct(closes, 5)` mengambil baris
ke-5 dari belakang, bukan **sesi** ke-5 — untuk emiten sparse, "return 5 hari" bisa berarti
return 3 bulan. Contoh nyata: PACK punya baris 09-07 lalu 09-17.
**Patch:** reindex `closes` ke `trading_days(wh, as_of, 21)`; kalau ada lubang di 6 sesi terakhir,
`return_5d = None` (sudah diperlakukan "tidak tersedia", bukan nol). Sekalian syaratkan
`len(closes) >= 20` supaya emiten dengan 2 baris tidak ikut diranking.
**Catatan desain:** karena `fetch-close` dikeluarkan dari sapuan (32 halaman/hari), universe
Tier-1 secara efektif adalah **39 emiten backfill + most-traded harian**. Itu sah kalau dinyatakan;
saat ini `ARCHITECTURE.md` §5 masih mengklaim "market-wide".

### B4 · Biaya PFD di katalog perencana salah 6× — `core/probes/fundamental.py` + `core/sectors/routing.py` (Melco) 🟠 ⬜
`cost_estimate("price_fundamental") = 6` = `fetch-close` (1) + `fetch-quarterly-financials`
(`units=5`). Tapi: (a) probe **tidak pernah memanggil** `fetch-close` — ia membaca `price_history`
dari warehouse, endpoint itu hanya dipakai sebagai label bukti; (b) ledger mencatat
**16 panggilan `fetch-quarterly-financials`, semuanya 1 kredit** walau `n_quarters=8`. Biaya nyata
PFD = **1**, perencana melihat **6** dan menghindarinya. Ini kebalikan dari "pemilihan sadar biaya".
**Patch:** `endpoints = ("fetch-quarterly-financials",)`, `units=1` di routing dengan `cost_note`
menunjuk ledger; `make docs`. Label bukti `pfd.return_90d` tetap boleh menyebut
`fetch-daily-transaction` (yang benar-benar sumbernya), bukan `fetch-close`.

### B5 · Cron tidak mengekspor data web; ekspor menyertakan fixture — `.github/workflows/daily.yml` + `core/export/to_json.py` (Melco, Nadhilla) 🔴 🟨
Tahap 2 menulis `runs/investigations/` tapi **tidak** menjalankan `python -m core.export.to_json`,
sehingga `web/public/data/index.json` beku sejak 11 Sep. `TRANSCRIPT_SOURCES` menggabungkan
`fixtures/transcripts/` → FIXA/FIXB/FIXC tampil di landing sebagai investigasi nyata.
**Patch:** `to_json` default **tanpa** fixture (`--with-fixtures` untuk tes UI), tambah langkah
cron setelah Tahap 2 + tambahkan `web/public/data/` ke `git add`. Tambah tes: ekspor default
tidak memuat simbol yang berawalan `FIX`.

> **🟨 Separuh.** Sisi `to_json.py` sudah dikerjakan Nadhilla di PR #13 — `--with-fixtures`
> sekarang opt-in, default hanya `runs/investigations/`. Tapi PR #13 **masih terbuka**, jadi
> belum di `main`. Sisi `daily.yml` **belum sama sekali**: tidak ada langkah `python -m
> core.export.to_json` di cron, dan `web/public/data/` belum masuk `git add`. Tesnya juga belum
> ada. Sampai keduanya masuk, `index.json` tetap beku walau cron sukses.

### B6 · `corporate_actions` bocor 1 kredit per hari untuk emiten bersih — `core/probes/structural.py` (Melco) 🟡 ⬜
`ctx.ensure("corporate_actions", ..., where="symbol = ?", min_rows=1)` dengan params
`{"start", "end": as_of}`: emiten tanpa aksi korporasi selalu punya 0 baris → tarik lagi tiap
hari, dan karena `end` berubah, cache disk tidak pernah kena. Berbeda dari `suspensions`/`filings`
yang diperiksa market-wide. **Patch:** simpan penanda "sudah disapu untuk symbol ini sampai
tanggal X" — paling sederhana: `params` tanpa `end` (rentang tetap `start` → hari ini tidak perlu
dikunci ke as_of untuk aksi korporasi 24 bulan), sehingga kunci cache stabil selama sebulan.

### B7 · Langkah terbuang saat pagu tidak cukup — `core/agent/investigator.py` (Hamzah) 🟡 ✅
```python
if not budget.can_afford(biaya) and budget.remaining <= 0: break
```
Sisa 1 kredit, probe berikut 3 kredit → loop **tetap menjalankan** probe; `Context.ensure` menolak
tarikan, probe pulang `unavailable`, satu langkah dan satu panggilan LLM terbakar untuk hasil
kosong. Transkrip lalu menampilkan "probe menyerah" yang terbaca seperti kegagalan data.
**Patch:** kalau `not can_afford(biaya)`: lewati probe ini (catat di `stopped_by` kalau antrean
habis karenanya), coba probe berikut yang terjangkau; kalau tidak ada, `break` dengan alasan
"pagu tidak cukup untuk probe tersisa".

### B8 · Perbaikan HEAD belum di `main`; cron memakai `main` (Hamzah) 🔴 ✅
Commit `3e667be` (fresh=True + fase kredit) hanya ada di `fix/hamzah/probe-data-basi`. Sampai
di-merge, Tahap 2 malam ini mengulang pola 0 kredit. Menyentuh `core/probes/` (milik Melco) —
buka PR, sebut eksplisit.

### B9 · Investigasi ulang emiten yang sama tiap hari tanpa jeda — `tools/investigate_watchlist.py` (Melco/Hamzah) 🟡 ✅
Top-3 watchlist = ASLI/NICK/JAWA selama 9 hari. Tidak ada aturan "sudah diselidiki kemarin dengan
keyakinan 0,8 → lewati kecuali sinyal Tier-1 berubah". Kredit `daily` terbakar untuk delta nol,
dan memori tidak pernah dipakai untuk **memilih**, hanya untuk merencanakan.
**Patch:** di `run()`: `Memory.recall(symbol, before=as_of)`; kalau `as_of - recall.as_of <= 2`
hari bursa **dan** `recall.confidence >= 0.6` **dan** skor seleksi watchlist berubah < 0,05 →
lewati, ambil kandidat berikutnya. Catat keputusan ini di log run (itu perilaku agentik yang
terlihat: "tidak menyelidiki karena tidak ada yang berubah").

---

## 2. Lubang desain agen

Ini bukan bug; kode berjalan sesuai tulisan. Tapi masing-masing membuat agen lebih dangkal dari
yang `ARCHITECTURE.md` §3 klaim, dan juri yang membaca `runs/investigations/*.json` akan melihatnya.

### D1 · Penyelidik buta terhadap langkah sebelumnya — `investigator.py::_decide` ✅
Prompt tiap langkah hanya memuat: rationale rencana, **hasil probe barusan**, daftar nama probe
yang mengantre, sisa pagu, katalog. **Tidak ada** sub-skor dan bukti dari langkah 1..n-1.
Keputusan `conclude` di langkah 3 dibuat tanpa tahu langkah 1 memberi 100/100. Ini sebab
transkrip berisi kalimat seperti "Volume_anomaly sebelumnya sudah mengonfirmasi…" (JAWA 11 Sep)
— model **menebak** dari rationale, bukan membaca. Perbaikan: sertakan ringkasan
`_describe(r)` untuk semua `inv.results` (≤6 baris, murah), plus skor komposit sementara dari
`score(inv.results)` (deterministik, boleh dilihat LLM — ia memilih rute, bukan angka).

### D2 · Tidak ada gerbang keyakinan minimum sebelum `conclude` ✅
NICK: 30→85→56→71→36→**100**→64→**0**→52 dalam 9 hari. NICK 17 Sep: satu probe
(`broker_concentration`), keyakinan 0,25, skor 100, band "sangat waspada". NICK 21 Sep: satu
probe, skor 0, "normal". Kode mengizinkan `conclude` kapan saja. Perbaikan di `investigate()`:
kalau `d.next_action == "conclude"` dan `score(inv.results).confidence < MIN_KEYAKINAN (0,4)` dan
masih ada probe terjangkau di antrean → **tolak conclude**, ubah jadi `continue`, `reason` diberi
awalan "[keyakinan 25% < 40%, dilanjutkan]". Kalau pagu memang tidak cukup, biarkan `conclude` dan
transkrip jujur soal keyakinannya. Ini pagar ke-5 dan layak masuk `guardrails.py` + tes.

### D3 · Perencana tidak menerima sinyal watchlist ✅
`tier1_market.screen` sudah menghitung `volume_z`, `return_5d/20d`, `small_cap`, `peristiwa`,
`alasan` — lalu `runner.tier1_signals` menghitung ulang versi yang lebih kasar (rasio volume
terhadap median seluruh riwayat, perubahan harga sejak baris pertama = bisa 8 bulan) dan
`kapitalisasi` hanya ada untuk 16 emiten. Perbaikan: `investigate_symbol(..., signals=...)`
menerima dict dari `watchlist.json` bila ada; `tier1_signals` jadi cadangan.

### D4 · Memori hanya skor/band/keyakinan/kredit — `memory.py::Recollection` ✅
`transcript_path` disimpan tapi tidak dibaca. Perencana diminta "fokus pada apa yang berubah"
tanpa tahu komponen apa yang kemarin sudah 100/100 dan mana yang belum pernah dijalankan.
Akibat terukur: `free_float` (tidak berubah harian, umur data 15 hari) dibeli ulang hampir tiap
hari. Perbaikan: `briefing()` memuat tabel `komponen: sub_skor (umur bukti)` dari transkrip
sebelumnya + kalimat aturan "bukti berumur < N hari untuk FFS/SSS tidak perlu dibeli ulang".
Nol perubahan kontrak — hanya isi prompt.

### D5 · Tingkat fallback tidak diukur di mana pun ⬜
Fakta dari 30 transkrip: 10 rencana cadangan (`rationale` berawalan "Rencana cadangan"),
10 narasi `template`, TRUK 9 Sep 100% cadangan. Tidak ada metrik ini di `to_json`, README,
maupun eval. Tanpa angka ini kita tidak tahu apakah T-D (§3) berhasil. Perbaikan: hitung di
`to_json.moment_kinds` → `index.json` memuat `{"planner_llm": bool, "llm_decisions": n,
"fallback_decisions": n}`; catatan: `Investigation.llm_decisions` sudah dihitung di
`investigator.py` tapi **tidak masuk transkrip** (kontrak beku) — deteksi dari teks `reason`
"Keputusan cadangan berbasis aturan" cukup.

### D6 · Pagar "maks 8 langkah" tidak pernah bisa tercapai ✅
Enam probe, masing-masing sekali → maksimum 6 langkah. `PANTAU_MAX_STEPS=8` adalah klaim dokumen.
Turunkan default ke 6 atau, lebih jujur, hitung dari `len(PROBES)`.

### D7 · Sinyal ke penyelidik tidak memuat umur bukti ✅
`_describe` mencetak `label: display`, bukan `as_of`. Agen tidak bisa tahu bahwa broker summary
yang ia baca berumur 15 hari (persis bug HEAD, yang akan terulang untuk tabel tanpa `fresh=True`).
Tambahkan `(per DD-MM)` di tiap bukti dalam prompt.

### D8 · Eval tidak bisa diulang untuk mengukur kebisingan ⬜
`llm.py` cache berkunci `(system, messages, tools, prompt_version, max_tokens, temperature)` →
menjalankan eval dua kali = hasil identik dari cache. `reports/agent-eval-ringkasan.md` sudah
menyimpulkan kebisingan ±6–12 pp dari **dua** jalan; untuk rentang yang bisa dikutip perlu
`--repeat N` yang menambahkan `-rN` ke `prompt_version` untuk lengan agen saja. Nol kredit Sectors.

### D9 · `baseline_credits = max(total, 16)` — `adjudicator.py` ⏸
Kalau agen membelanjakan 18, "baseline" ikut 18 dan penghematan tampak 0% bukan negatif. Ganti ke
`baseline_credits(symbol)` apa adanya; kontrak tidak mensyaratkan `credits_total <= baseline`
(cek `contracts/check.py` — kalau ya, itu invarian yang harus dilonggarkan lewat CHANGES, bukan
disiasati).

> **⏸ Dicek: ya, kontraknya memang mensyaratkan.** `contracts/check.py:85` menegakkan
> `credits_total <= baseline_credits`, dan `contracts/` beku sejak 12 Sep. Jadi `max(total, 16)`
> bukan siasat penulis `adjudicator.py`, melainkan satu-satunya cara memenuhi invarian saat agen
> membelanjakan lebih dari baseline. Memperbaikinya di kode = melanggar kontrak; harus lewat
> usulan `contracts/CHANGES.md`. **Belum diajukan** — keputusan pengajuan ada di luar lajur satu
> orang, dan di sisa waktu sebelum freeze biayanya lebih besar daripada manfaatnya. Yang penting
> diketahui juri: angka "hemat 0%" di transkrip yang membelanjakan lebih dari baseline **bukan
> kebetulan, dan bukan kebohongan yang disengaja** — itu invarian kontrak yang menabrak
> kenyataan.

---

## 3. Terobosan — diranking dampak ÷ usaha

| # | Terobosan | Berkas | Pemilik | Ukuran | Menutup |
| --- | --- | --- | --- | --- | --- |
| T1 | **Konteks bukti berjalan + gerbang keyakinan minimum** | `investigator.py`, `guardrails.py` | Hamzah | ½ hari | D1, D2, D7, B7 |
| T2 | **Memori bersub-skor + jeda seleksi** | `memory.py`, `tools/investigate_watchlist.py` | Hamzah, Melco | ½ hari | D4, B9 |
| T3 | **Jalur permintaan via GitHub Issue** | `daily.yml`, `tools/investigate_watchlist.py`, web `SearchBox` | Melco, Nadhilla | 1 hari | produk bisa dipakai orang |
| T4 | **Penyedia LLM produksi → Claude + metrik fallback** | `daily.yml`, `to_json.py` | Hamzah, Melco | 2 jam | D5, gerbang T1 |
| T5 | **Watchlist benar** (B2, B3) | `tier1_market.py` | Melco | 2 jam | B2, B3 |
| T6 | **Timeout pagar nyata + tes** (B1) | `guardrails.py`, `tests/agent/` | Hamzah | 1 jam | B1 |
| T7 | **Ekspor di cron, tanpa fixture** (B5) | `daily.yml`, `to_json.py` | Melco, Nadhilla | 1 jam | B5 |
| T8 | **Biaya PFD benar** (B4) + `fetch-news` sebagai sinyal Tier-1 | `fundamental.py`, `routing.py`, `runner.py` | Melco, Hamzah | 2 jam + 3 jam | B4, inovasi MCP |
| T9 | **`evals --repeat N`** | `agent_eval.py`, `portfolio.py`, `llm.py` | Hamzah | 2 jam | D8 |
| T10 | **UI membaca transkrip, bukan teks tetap** | `web/app/investigasi/[id]/page.tsx` | Nadhilla | 2 jam | klaim memori palsu di UI |

### T1 · Konteks bukti berjalan + gerbang keyakinan minimum (paling berpengaruh ke "agen berpikir")
Di `_decide`, tambahkan blok:
```
Bukti terkumpul sejauh ini:
- volume_anomaly → 100/100 (per 22-09): Z-score 12,8σ; rasio 9,9×
- free_float     → 28/100 (per 07-09): Free float 37%
Skor sementara: 68 (waspada), keyakinan 40% — bobot tercakup VAS 0,22 + FFS 0,18.
Komponen berbobot besar yang BELUM diperiksa: BCI 0,25 (3 kredit), FRD 0,15 (2 kredit).
```
Semua angka di blok ini deterministik dari `score(inv.results)`; LLM tetap hanya memilih rute.
Di `investigate()`, sebelum `if d.next_action == "conclude"`:
```python
komp = score(inv.results)
terjangkau = [p for p in antrean if budget.can_afford(PROBES[p].cost_estimate(symbol))]
if d.next_action == "conclude" and komp.confidence < MIN_KEYAKINAN and terjangkau:
    d = d.model_copy(update={"next_action": "continue"})
    alasan = f"[keyakinan {komp.confidence:.0%} < {MIN_KEYAKINAN:.0%}, dilanjutkan] {alasan}"
```
`MIN_KEYAKINAN = 0.4` di `guardrails.py` (env `PANTAU_MIN_CONFIDENCE`). **Tes:** FakeLLM yang
selalu `conclude` setelah probe pertama; dengan 2 probe murah di antrean, investigasi harus
berlanjut sampai keyakinan ≥ 0,4 atau antrean habis. Tes kedua: pagu 1 kredit → `conclude`
diizinkan dengan keyakinan rendah (jujur, bukan dipaksa).

### T2 · Memori bersub-skor + jeda seleksi
`Recollection` tambah field `components: dict[str, tuple[float|None, date|None]]` diisi dari
`transcript_path` (baca JSON, ambil `components` + `as_of` bukti pertama tiap komponen).
`briefing()`:
```
Investigasi 1 hari lalu (22-09): skor 62 (waspada), keyakinan 73%, 3 kredit.
  VAS 100 (bukti per 22-09) · FFS 28 (per 07-09) · BCI 55 (per 22-09) · PFD/FRD/SSS belum pernah.
Yang bergerak lambat dan masih segar tidak perlu dibeli ulang: FFS (15 hari), SSS.
Fokus pada apa yang berubah: volume hari ini, arus asing, konsentrasi broker.
```
Di `investigate_watchlist.run`: aturan jeda B9. Log run mencetak "NICK dilewati: diselidiki
kemarin (keyakinan 92%), sinyal seleksi tidak berubah" — bukti memori di tahap **seleksi**.

### T3 · Jalur permintaan via GitHub Issue (nol backend, tetap otonom, tercatat)
- `.github/ISSUE_TEMPLATE/selidiki.yml`: satu field `symbol` (regex `^[A-Z]{4}$`), label otomatis
  `selidiki`.
- `tools/investigate_watchlist.py --requests`: baca issue terbuka berlabel `selidiki` lewat
  `gh issue list --label selidiki --json number,title,body` (token `GITHUB_TOKEN` bawaan
  Actions, `permissions: issues: write`), validasi simbol terhadap `free_float.parquet` (961
  emiten — daftar emiten sah tanpa kredit), masukkan ke **depan** antrean, maksimal 3 per hari
  (pagu `daily`), lalu setelah transkrip tersimpan: `gh issue close N --comment "<tautan
  transkrip>"`. Simbol tak sah → tutup dengan komentar "bukan kode emiten IDX".
- Web: `SearchBox` yang tidak menemukan simbol menampilkan tautan
  `https://github.com/<repo>/issues/new?template=selidiki.yml&title=selidiki:+XXXX`.
- `workflow_dispatch` input `symbols` (koma) untuk demo langsung.
**Tes:** `run()` dengan `requests=["BBCA"]` memasukkan BBCA sebelum top-N; simbol tak sah
dilewati dengan alasan. Injeksi `gh` di-mock.

### T4 · Penyedia LLM produksi → Claude, dan ukur
`daily.yml`: `PANTAU_LLM_PROVIDER: claude`, secret `ANTHROPIC_API_KEY`. `core/llm.py` sudah
mendukung; `supports_temperature=False` untuk Claude berarti eval kehilangan `temperature=0` —
terima, atau kirim `output_config.effort` rendah. Setelah satu malam cron, hitung dari
`runs/investigations/`: % rencana LLM, % keputusan LLM (dari `reason` tidak berawalan
"Keputusan cadangan"), % narasi `llm`. Ekspor ke `index.json` (D5) dan `make credits` cetak juga
ringkasan LLM dari `data/llm_ledger.jsonl` (sudah ada datanya, belum ada pembacanya).

### T8b · `fetch-news` sebagai sinyal Tier-1 ke perencana (inovasi MCP tanpa mengubah kontrak)
Pertanyaan Rina yang sebenarnya: "ramai karena ada berita, atau ramai tanpa alasan?". Probe baru
= perubahan kontrak (`ProbeName` beku) → **tidak**. Yang bisa: di `runner.tier1_signals`, kalau
`client` ada dan pagu mengizinkan, panggil `fetch-news` (1 kredit, via MCP, tercatat ledger)
untuk 5 judul terbaru + tanggal → `signals["berita_terbaru"]`. Perencana yang tahu "ada berita
akuisisi 2 hari lalu" memilih `price_fundamental` alih-alih `broker_concentration` — perutean
adaptif yang bisa ditunjuk. Simpan judul ke `plan.rationale` **tidak** (LLM yang menulis) —
cukup ke log run. Tambahkan `fetch-news` ke `routing.py` (tier 2, 1 kredit, mcp). Lakukan hanya
kalau T1–T7 hijau pada 24 Sep.

---

## 4. Urutan eksekusi & batas lajur

```
Sel 23  pagi   B8 merge HEAD → main (PR, sebut core/probes/ milik Melco)
        siang  T6 timeout (Hamzah) · T5 watchlist (Melco) · T7 ekspor di cron (Melco+Nadhilla)
        sore   verifikasi cron: kredit > 0, watchlist berubah, index.json baru
Rab 24         T1 + T2 (Hamzah) · T3 (Melco cron, Nadhilla web) · T4 (secret + env) · T8 biaya PFD (Melco)
Kam 25         T9 eval --repeat 3 (Hamzah, nol kredit Sectors) · T10 UI (Nadhilla) · T8b hanya kalau semua hijau
               🔒 feature freeze 23:59 — setelah ini hanya bugfix + dokumen
Jum 26–Sen 28  cron jalan 3 hari bursa dengan kode final = bukti otonom yang sebenarnya
```

### Sisa pekerjaan per 24 Sep pagi — 2 hari sebelum freeze

| Sisa | Pemilik | Terhalang oleh |
| --- | --- | --- |
| **T5** (B2, B3) — watchlist monoton, `return_5d` atas sesi | Melco | — **kerjakan lebih dulu**: ini yang memilih emiten mana yang diselidiki cron nanti malam |
| **T8** (B4) — biaya PFD benar | Melco | — |
| **B6** — kebocoran kredit `corporate_actions` | Melco | — |
| **D5** — metrik fallback ke `index.json` | Hamzah | — |
| **T9** (D8) — `evals --repeat N` | Hamzah | — nol kredit Sectors |
| **T7** (B5) — langkah ekspor di `daily.yml` + merge PR #13 | Melco + Nadhilla | — sisi `to_json` sudah beres di PR #13, sisi cron belum ada |
| **T3** — jalur permintaan via GitHub Issue | Melco + Nadhilla | — |
| **T10** — UI membaca transkrip | Nadhilla | — |
| **T4** — penyedia LLM → Claude | — | **secret `ANTHROPIC_API_KEY` belum dipasang di repo**; tidak bisa dikerjakan dari sisi kode |
| **D9** — `baseline_credits` | — | **kontrak beku**; perlu usulan `contracts/CHANGES.md` |
| **T8b** — `fetch-news` sebagai sinyal Tier-1 | — | **sengaja dilewat**: audit ini sendiri mensyaratkan "hanya kalau T1–T7 hijau pada 24 Sep", dan T5 belum |
| **N2** — skor berbanding terbalik dengan kedalaman | — | struktural, menyentuh `band` di kontrak → pasca-freeze |

Di luar audit: dashboard **riwayat analisa agen** (`feat/hamzah/riwayat-agen`, di atas PR #13)
menampilkan jejak skor per emiten, delta antar hari, momen agentik, dan cakupan `n/6 komponen`.
Belum di-PR — menunggu PR #13 Nadhilla masuk `main` dulu. Ini yang membuat N2 terlihat.

Aturan kepemilikan `TASK.md` tetap: Hamzah tidak mengedit `core/probes/`, `core/ingest/`,
`.github/`; perbaikan B2–B6 diserahkan ke Melco lewat PR ini sebagai spesifikasi. Kalau Melco
tidak tersedia 24 Sep, Hamzah boleh mengerjakan B2/B4/B5 di branch terpisah dengan catatan
eksplisit di pesan commit — presedennya sudah ada di `3e667be`.

---

## 5. Tes yang wajib ditambah (semua nol jaringan)

| Tes | Berkas | Menjaga |
| --- | --- | --- |
| ✅ timeout kembali < 1 detik untuk probe `sleep(2)` | `tests/agent/test_guardrails.py` | B1 |
| ⬜ `_clip`/normalisasi monoton per sinyal | `tests/ingest/test_tier1.py` | B2 |
| ⬜ `return_5d` None bila 6 sesi terakhir berlubang | `tests/ingest/test_tier1.py` | B3 |
| ⬜ `cost_estimate("price_fundamental") == cost_of("fetch-quarterly-financials")` | `tests/probes/test_probes.py` | B4 |
| ⬜ ekspor default tidak memuat simbol `FIX*` | `tests/export/` | B5 |
| ✅ `conclude` ditolak saat keyakinan < 0,4 dan ada probe terjangkau | `tests/agent/test_investigator.py` | D2 |
| ✅ `conclude` diizinkan saat pagu habis walau keyakinan rendah | idem | D2 |
| ✅ prompt penyelidik memuat bukti semua langkah sebelumnya | idem | D1 |
| ✅ `briefing()` menyebut sub-skor dan umur bukti dari transkrip sebelumnya | `tests/agent/test_memory.py` | D4 |
| ✅ kandidat dilewati bila diselidiki ≤2 hari lalu dengan keyakinan ≥0,6 | `tests/test_investigate_watchlist.py` | B9 |
| ⬜ permintaan Issue masuk depan antrean; simbol tak sah ditolak | idem | T3 |
| ⬜ `--repeat 3` menghasilkan tiga jalan yang tidak identik pada FakeLLM berbibit | `tests/evals/` | D8 |

---

## 6. Yang tidak perlu disentuh

Sudah benar dan tertes: `CreditAwareClient` (cache, ledger, retry 429, redaksi), `Budget`
(preview/commit/refund, batas 2 eskalasi), validator sitasi + nama emiten, `composite.score`
(komponen None ≠ nol), point-in-time di `Warehouse.connect`, `vocab_guard` termasuk `Step.reason`
(HEAD), `_queue` dedup, gerbang eskalasi (sudah diperbaiki 13 Sep), CI empat gerbang + pemeriksaan
kunci di riwayat. Jangan habiskan hari yang tersisa untuk merapikan yang sudah bekerja.

PANTAU adalah alat informasi dan analisis, bukan saran investasi.
