# TASK_MELCO.md — Data, Transport & Probe

**Lajur: fondasi.** Semua orang menunggu lu di awal, tidak ada yang menunggu lu di akhir.
Misi satu kalimat: **membuat data Sectors masuk ke mesin dengan murah, terukur, dan bisa diulang tanpa jaringan.**

Master plan: [`TASK.md`](TASK.md) · Desain: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Alasan: [`RESEARCH.md`](RESEARCH.md)
Tugas di file ini **termasuk QA-nya sendiri**. Video & submission dikerjakan bareng di akhir.

---

## Milik lu

```
core/sectors/     client.py · transport_rest.py · transport_mcp.py
                  routing.py · catalog.py · schemas.py
core/ingest/      tier1_market.py · backfill.py
core/probes/      base.py · broker.py · volume.py · fundamental.py
                  freefloat.py · foreign.py · structural.py · registry.py
data/             warehouse/*.parquet · credit_ledger.jsonl · cache/
.github/workflows/daily.yml
Makefile · konfigurasi CI · docs/endpoint-costs.md · docs/mcp-catalog.md
tests/sectors/ · tests/probes/
```

**Jangan sentuh:** `core/agent/`, `core/scoring/`, `core/narrative/`, `evals/` (Hamzah) · `web/`, `core/export/`, `fixtures/` (Nadhilla).

## Kontrak lu

**Lu menghasilkan** — dipakai Hamzah:
```python
class ProbeResult(BaseModel):
    sub_score: float          # 0-100
    evidence: list[EvidenceEntry]
    credits_spent: int

class Probe(Protocol):
    name: str
    def cost_estimate(self, symbol: str) -> int: ...
    def run(self, symbol: str, ctx: Context) -> ProbeResult: ...
```
Plus `data/warehouse/*.parquet` dan `registry.py` (definisi tool untuk LLM: nama, deskripsi, skema argumen, biaya).

**Lu mengonsumsi:** tidak ada. Lu fondasi — bisa mulai detik ini juga.

✅ **`ProbeResult`, `Probe`, dan `ProbeContext` sudah beku** di `contracts/schemas.py`, sudah direview terpusat. Perhatikan `ProbeContext.as_of`: probe **wajib point-in-time** — satu probe saja yang membaca data setelah `as_of` akan membocorkan lookahead ke kalibrasi Hamzah. Tegakkan di `tests/probes/`.

⚠️ Butuh bentuknya berubah? Ajukan di [`contracts/CHANGES.md`](contracts/CHANGES.md) — **jangan** edit `schemas.py` langsung.

---

## Fase

> **Status per 8 Sep.** `[x]` = kode ada dan tertes tanpa jaringan (182 tes hijau,
> `make ci`). `[~]` = kode ada, tapi belum bisa dibuktikan tanpa **API key** atau
> tanpa **cron pertama yang benar-benar jalan** — jangan dianggap selesai.
> `[ ]` = belum dikerjakan.
>
> **Yang memblokir sisanya, semuanya satu hal: `SECTORS_API_KEY` belum ada di
> `.env` maupun GitHub Secrets.** Begitu key masuk, urutannya:
> `make spike` (ukur biaya aktual, ganti asumsi) → `make backfill --dry-run` →
> tahap 1 & 2 backfill → commit `data/warehouse/` → nyalakan cron.

### M1 · Jalur REST hidup · 8–10 Sep
> Prioritas mutlak. Jangan sentuh MCP sebelum blok ini hijau.

- [x] `client.py` — `CreditAwareClient` sebagai gateway tunggal: cache disk permanen berkunci hash `(endpoint, params)`, ledger `data/credit_ledger.jsonl`, pagu per fase yang **menolak** (raise, bukan warning), retry + backoff, redaksi API key di seluruh log `[AD-3][AD-5]`
- [x] `transport_rest.py` — `httpx`, header `Authorization: <key>`, base `https://api.sectors.app/v2`
- [x] `schemas.py` — model pydantic dari respons spike F0
- [~] `docs/endpoint-costs.md` — biaya kredit **aktual** tiap endpoint (1/2/3). Hamzah memakai angka ini untuk menganggarkan perencana
- [x] `core/ingest/tier1_market.py` — sapuan market-wide, target **≤6 kredit/hari**: `fetch-close`, `fetch-most-traded-stocks`, `fetch-companies-top-changes`, `fetch-suspensions`, `fetch-filings`
- [x] DuckDB warehouse + skema tabel; `make credits`
- [x] **QA:** cache hit tidak menambah ledger · pagu terlampaui → raise · key tidak pernah muncul di log · respons rusak → error jelas, bukan `KeyError`

### M2 · Enam probe · 10–12 Sep
> ✅ **Gerbang: satu probe hijau paling lambat 10 Sep** — Hamzah butuh ini untuk mengganti stub.

- [x] `probes/base.py` — kontrak `Probe`, `Context`, konstruksi `EvidenceEntry`
- [x] `broker.py` — **BCI**: HHI net buy + pangsa 3 broker teratas
- [x] `volume.py` — **VAS**: z-score volume vs baseline 90 hari
- [x] `fundamental.py` — **PFD**: return vs perubahan laba/valuasi
- [x] `freefloat.py` — **FFS**: kelangkaan saham beredar
- [x] `foreign.py` — **FRD**: arus asing keluar saat harga naik
- [x] `structural.py` — **SSS**: suspensi, insider filings, corporate actions
- [x] `registry.py` — definisi tool yang diekspos ke LLM
- [x] **QA:** tiap probe jalan pada `fixtures/warehouse-mini/` **tanpa jaringan** · ticker baru IPO (data pendek) tidak crash · ticker tersuspend tidak crash · data hilang → `sub_score` None + alasan, bukan nol diam-diam
- [ ] Kabari Hamzah tiap kali satu probe hijau — dia mengganti stub satu per satu

### M3 · Backfill untuk kalibrasi · 10–12 Sep · anggaran 400 kredit
> Jalan paralel dengan M2. Hamzah **terblokir total** tanpa ini.

- [x] `backfill.py` — 120 hari bursa `fetch-close`; suspensi & filings 24 bulan; Tier-2 untuk himpunan positif + kontrol
- [ ] Serahkan ke Hamzah: warehouse terisi + daftar suspensi mentah beserta alasan resminya
- [ ] Commit `data/warehouse/*.parquet` ke repo — ini yang membuat juri bisa jalan tanpa API key `[AD-2]`

### M4 · Cron hidup · **paling lambat Sen 14 Sep** 🔴
> Gerbang keras tim. Jam bukti operasi otonom mulai berdetak di sini. Tidak bisa dikejar belakangan.

- [x] `.github/workflows/daily.yml` — cron **10:30 UTC = 17:30 WIB**, Sen–Jum
- [ ] Tahap 1 (14 Sep): sapuan Tier-1 + watchlist → commit `runs/YYYY-MM-DD/` + `run.log`
- [ ] Tahap 2 (±19 Sep, setelah agen Hamzah jalan): panggil agen untuk top-N → commit `runs/investigations/`
- [ ] Verifikasi eksekusi pertama yang benar-benar **tak disentuh manusia**
- [ ] Screenshot konfigurasi schedule → simpan untuk video
- [~] **QA:** cron gagal → workflow merah dan terlihat, bukan diam · commit otomatis tidak menimpa kerja orang

### M5 · Transport MCP · 12–15 Sep
> ⚠️ **Peningkatan, bukan prasyarat.** Rubrik berbunyi "Sectors API *or* MCP". Kalau belum jalan pada **11 Sep**, konsultasi tim → kemungkinan besar REST-only. `TASK.md` §Rencana Cadangan

- [x] `transport_mcp.py` — klien MCP **tulis sendiri** (`mcp` SDK, Streamable HTTP) ke `https://sectors-mcp.supertype.ai/mcp`, header `Authorization: Bearer <key>`. Tiap tool call dicegat dan dimeter persis seperti REST `[AD-7]`
- [x] `routing.py` — tabel endpoint → transport. **Keputusan transport tidak pernah diserahkan ke LLM**
- [x] `catalog.py` — katalog tool MCP **beserta harga kredit**, disajikan ke perencana Hamzah. Ini yang membuat klaim "innovative use of MCP" kita punya isi
- [x] `docs/mcp-catalog.md` — dump katalog + perbandingan biaya MCP vs REST untuk endpoint yang sama
- [~] **QA:** tool call MCP muncul di ledger dengan biaya benar · MCP mati → fallback REST kalau endpoint-nya ada di kedua transport, bukan seluruh pipeline tumbang

### M6 · Infrastruktur & jaga · 15–25 Sep
- [x] `Makefile`: `demo` · `pipeline` · `credits` · `test`
- [x] CI: `ruff` + `pytest` + **larangan kosakata** (grep "beli", "jual", "target harga", "rekomendasi", "cuan", "pasti naik" pada seluruh string output, **termasuk narasi LLM tersimpan** milik Hamzah) `[K5]`
- [ ] Jaga cron tetap hijau tiap hari bursa sampai freeze
- [ ] Laporkan posisi kredit ke tim tiap Minggu malam
- [ ] **25 Sep:** verifikasi `runs/` memuat **≥10 hari bursa berturut-turut**

---

## Anggaran kredit — lu penjaganya

Lu satu-satunya yang boleh membelanjakan kredit lewat kode. **Nol `curl` manual, nol Postman.**

| Fase | Pagu |
| --- | --- |
| Spike + pengembangan probe | 120 |
| Backfill + kalibrasi | 400 |
| Eval agen (dipakai Hamzah, lewat kode lu) | 130 |
| Operasi harian | 250 |
| Cadangan | 100 |

Alarm di 70% dan 90%. Kalau ada yang minta kredit di luar pagu, jawabannya tidak — itu gunanya pagu ditegakkan di kode.

## Gerbang yang lu pegang
| Tanggal | Gerbang |
| --- | --- |
| 10 Sep | Satu probe hijau — Hamzah bisa lepas dari stub |
| 12 Sep | Warehouse terisi + enam probe hijau |
| **14 Sep** | 🔴 **Cron hidup** — tidak bisa ditawar |
| 11 Sep | Putusan MCP: lanjut atau REST-only |

## Kalau lu terblokir
Endpoint tidak sesuai asumsi → **jangan diam**, langsung ke `TASK.md` §Rencana Cadangan dan kabari tim hari itu juga. Batas keputusan untuk masalah bentuk data adalah **9 Sep**; lewat itu, mengubah desain jadi mahal.

## Selesai kalau
`make demo` jalan di mesin bersih tanpa API key · enam probe tertes tanpa jaringan · `runs/` berisi ≥10 hari bursa artefak cron · ledger kredit ter-commit dan konsisten · CI hijau.
