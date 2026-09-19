# MIDDLEWARE_CONTRACT.md — kontrak Agent ⇄ Middleware ⇄ Frontend (v1)

> **Status: PROPOSAL final v1, untuk di-sign-off bertiga (Ikhsan · Hamzah · Melco).**
> Disusun lajur Web (Nadhilla). Menfinalkan §6 di [`RENCANA_LIVE_AGENT.md`](../RENCANA_LIVE_AGENT.md).
> Perluasan kebijakan AD-1 yang dirujuk dokumen ini diajukan terpisah di
> [`contracts/CHANGES.md`](../contracts/CHANGES.md) → entri **C6**.
>
> **Dokumen ini TIDAK mengubah `contracts/`.** Semua bentuk `step`/`evidence`/`verdict`
> di bawah = **persis `contracts/schemas.py` v1.0** (dikutip, bukan diubah). Middleware
> hanya *men-stream* bentuk yang sudah beku — tak ada bump `schema_version`.

---

## 1. Prinsip (kenapa kontrak ini aman untuk lomba)

Dua bidang data terpisah (lihat RENCANA §2):

```
BIDANG STATIS  — di-freeze 25 Sep, INI yang dinilai, tak pernah butuh runtime
    runs/ → core/export/to_json.py → web/public/data → replay di frontend        [AD-1]

BIDANG LIVE    — chat & investigate interaktif; opsional, additive
    Frontend ⇄ Middleware (WS + REST) ⇄ Agent (proses backend)
```

Tiga janji yang membuat kontrak ini tidak bisa "menggagalkan demo":

1. **Drop-in, bukan UI baru.** Event live disusun agar mengisi **bentuk data yang persis
   sama** dengan yang sudah dipakai komponen statis hari ini (`AgentChat`,
   `ReplayTimeline`, `EvidenceVerdict`). Live-mode = ganti *sumber* (WS) — **nol** komponen ditulis ulang. Peta di §4 & §5 adalah inti kontrak ini.
2. **Degrade anggun.** Frontend cek `GET /health`. Middleware mati/tak terjangkau →
   frontend jatuh ke **walkthrough statis** (`AgentChat` yang sudah ada). Jalur yang
   dinilai tak pernah bergantung pada middleware.
3. **Grounding wajib di server.** Middleware **tidak pernah** meneruskan token bebas
   ke UI tanpa lolos validator sitasi + vocab-guard (§6). Chat yang mengarang atau
   memberi saran = diskualifikasi; gerbang ini bukan opsi.

---

## 2. Transport & amplop (envelope)

- **WebSocket** `wss://<host>/ws?session=<uuid>` — semua streaming (chat & investigate).
- **REST** — trigger, arsip, health check (§7).

Setiap pesan WS (dua arah) memakai amplop berversi yang sama:

```jsonc
{
  "v": 1,                 // versi kontrak middleware (dokumen ini)
  "type": "chat.token",   // lihat katalог §8
  "id": "msg_9f3…",       // ID percakapan/run — mengelompokkan semua event satu jawaban
  "seq": 12,              // urut monoton per `id`; frontend merakit ulang sesuai urutan ini
  "ts": "2026-09-20T14:40:03+07:00",  // RFC3339 beroffset (jujur soal WIB, sama seperti [C1#7])
  "data": { /* payload spesifik per type */ }
}
```

`id` + `seq` membuat perakitan deterministik walau paket datang tak berurut. Frontend
mengabaikan `type` yang tak dikenalnya (forward-compatible).

---

## 3. Siklus hidup sesi

```
client  ── (WS connect ?session=uuid) ─────────────►  server
server  ── hello { credit_budget, models, live }  ──►  client   // kapabilitas + pagu awal
client  ── chat.ask | investigate ────────────────►  server
server  ── …stream event (§8)… ───────────────────►  client
server  ── done { id } ────────────────────────────►  client   // satu jawaban/run selesai
        (ulangi chat.ask/investigate selama sesi hidup)
heartbeat: server kirim `ping` tiap ≤20 dtk; client balas `pong`. 2× lewat → tutup.
```

- `hello.live=false` → middleware ada tapi agen/LLM tak siap (mis. tanpa API key). Frontend
  tetap boleh pakai `investigate` replay, tapi tandai chat sebagai walkthrough statis.
- Satu sesi = satu `credit_budget` (§6). Reconnect dengan `session` sama melanjutkan pagu.

---

## 4. Alur A — `chat.ask` → **bentuk `Answer` statis** (drop-in utama)

Bentuk yang dirender `AgentChat` hari ini (statis):

```ts
type Tool   = { label: string; ref: { kind: "evidence"|"step"|"section"; id: string } };
type Answer = { trace: string[]; text: string; tools: Tool[] };
```

Live-mode merakit `Answer` yang **sama** dari aliran event. Pemetaannya:

| Event live (server→client) | Mengisi bagian `Answer` | Aksi UI (identik dengan statis) |
| --- | --- | --- |
| `chat.start { id }` | buat pesan agen kosong (streaming) | gelembung agen muncul |
| `tool.call { name, label }` | `trace.push(label)` | baris jejak "▸ {label}" |
| `tool.result { ref }` | `tools.push({label, ref})` | tombol-tool (buka `ev-<id>`, lompat `.trail`/`.moments`) |
| `chat.token { text }` | `text += text` | teks mengetik bertahap |
| `chat.end { citations }` | finalisasi `text` (sudah tervalidasi §6) | render final |
| `error { reason }` | ganti jadi pesan aman | "maaf, …" tanpa mengarang |
| `done { id }` | tutup pesan | — |

**Konsekuensi:** `ref` pada `tool.result` memakai **id yang sudah ada di halaman** — `evidence.id`
(elemen `ev-<id>`), nomor `step`, atau anchor section — sehingga tombol live memicu aksi DOM
yang **sama persis** dengan tombol walkthrough statis. Tidak ada handler baru.

> Jadi `AgentChat.tsx` cukup diberi satu prop sumber: `mode="static"` merakit `Answer` dari
> transkrip (sekarang), `mode="live"` merakit `Answer` dari aliran WS. Sisa komponen tetap.

---

## 5. Alur B — `investigate` → **jejak penalaran = `schemas.py` v1.0**

`POST /investigate {symbol}` (atau WS `investigate`) memulai run; event di-stream:

| Event live | Bentuk payload (BEKU — dikutip dari `contracts/schemas.py`) | Komponen frontend |
| --- | --- | --- |
| `run.start { id, symbol, plan }` | `plan` = `Plan` (hypotheses[]/credit_budget_requested/rationale) | panel Rencana |
| `step { …Step }` | `Step` **utuh**: `step, hypothesis, probe, finding, next_action, new_probe, budget_granted, reason, credits_spent, credits_remaining` | `ReplayTimeline` (tipe `RenderStep`) |
| `tool.call { probe, args }` | niat panggilan probe (untuk animasi) | badge "menjalankan {probe}" |
| `tool.result { evidence }` | `evidence` = `EvidenceEntry` **utuh**: `id, label, value, display, probe, source_endpoint, source_params, source_transport, as_of, credits_spent` | `EvidenceVerdict` (buku bukti) |
| `verdict { … }` | `pantau_score, band, confidence, credits_total, baseline_credits, narrative, narrative_source, memory_ref` | gauge + verdict |
| `budget { spent, remaining }` | lihat §6 | meter kredit |
| `done { id }` | run selesai | — |

Karena `step`/`evidence`/`verdict` = bentuk `InvestigationTranscript` yang persis, frontend
memakai `lib/transcript.ts` + `ReplayTimeline` + `EvidenceVerdict` **tanpa perubahan** —
dan `detectMoments()` yang sama menandai 4 momen agentik dari `step` yang mengalir.

**Aturan konsistensi wajib** (agar transkrip live bisa disimpan jadi statis): sebuah run
yang `done` harus lolos `contracts/check.py` bila di-snapshot jadi `InvestigationTranscript`.
Artinya `sum(step.credits_spent) == credits_total`, `budget_granted` hanya di langkah
eskalasi, dst. — invarian [C1]/[C2] tetap berlaku. Middleware yang menyimpan run live ke
`runs/investigations/` = jembatan #2 bidang-live → bidang-statis.

---

## 6. Gerbang grounding, keamanan, & pagu (tidak bisa ditawar)

Middleware **wajib** menegakkan, di sisi server, sebelum `chat.end`/`verdict`:

1. **Validator sitasi** — reuse `core/narrative/validate.py`. Tiap angka di `text`/`narrative`
   harus punya `EvidenceEntry`; tiap token 4-huruf-kapital harus emiten yang diselidiki
   (cek `unsupported_tickers()`, [C3]). Gagal → **jangan stream keluaran LLM**; jatuh ke
   template deterministik dan set `narrative_source:"template"` / kirim `chat.end` bertanda template.
2. **Vocab-guard** — tolak/ganti keluaran yang memuat kosakata saran finansial (*beli, jual,
   target harga, rekomendasi, cuan, pasti naik*). Sama dengan CI Melco; ditegakkan juga di runtime.
3. **Disclaimer** tetap di frontend, permanen: *"PANTAU adalah alat informasi dan analisis,
   bukan saran investasi."* Middleware tak perlu mengirimnya.
4. **Pagu kredit per sesi** — `hello.credit_budget` (mis. 40). Tiap `tool.result` diikuti
   `budget { spent, remaining }`. Habis → `error { reason: "pagu habis" }`, hentikan tool-call.
   Reuse `core/agent/budget.py`. Cache jawaban umum untuk hemat.

---

## 7. REST

```
GET  /health                 → { ok: true, live: bool, ts }         // untuk degrade anggun
GET  /activity?limit=50      → { generated_at, events[] }           // BENTUK = public/data/activity.json
POST /investigate { symbol } → { id }                               // run di-stream via WS(id)
```

`GET /activity` sengaja berbentuk **sama** dengan `activity.json` statis, jadi `ActivityFeed`
membaca dari file (sekarang) atau dari endpoint (nanti) tanpa perubahan komponen. `/health`
adalah satu-satunya panggilan yang frontend butuh untuk memilih live vs statis.

---

## 8. Katalog event (ringkas)

```jsonc
// client → server
{ "type": "chat.ask",   "data": { "text": "kenapa SCCO waspada?" } }
{ "type": "investigate","data": { "symbol": "BBCA" } }
{ "type": "pong" }

// server → client
{ "type": "hello",       "data": { "credit_budget": 40, "live": true, "models": ["claude-…"] } }
{ "type": "chat.start",  "data": {} }
{ "type": "tool.call",   "data": { "name": "show_evidence", "label": "buka buku bukti", "probe": null, "args": {} } }
{ "type": "tool.result", "data": { "ref": { "kind": "evidence", "id": "ffs.data_age_days" } } }   // alur A
{ "type": "tool.result", "data": { "evidence": { /* EvidenceEntry utuh */ } } }                    // alur B
{ "type": "chat.token",  "data": { "text": "Skornya 59/100 …" } }
{ "type": "chat.end",    "data": { "citations": ["vas.zscore"], "narrative_source": "llm" } }
{ "type": "run.start",   "data": { "symbol": "BBCA", "plan": { /* Plan */ } } }
{ "type": "step",        "data": { /* Step utuh */ } }
{ "type": "verdict",     "data": { "pantau_score": 74, "band": "waspada", "confidence": 0.83,
                                    "credits_total": 18, "baseline_credits": 42,
                                    "narrative": "…", "narrative_source": "llm", "memory_ref": null } }
{ "type": "budget",      "data": { "spent": 12, "remaining": 28 } }
{ "type": "error",       "data": { "reason": "pagu habis" } }
{ "type": "ping" }
{ "type": "done",        "data": {} }
```

---

## 9. Pemilik & yang mengimplementasikan

| Bagian | Pemilik | Isi |
| --- | --- | --- |
| Kontrak ini + client WS + degrade + rakit `Answer`/trail | **Nadhilla** (Web) | frontend & API middleware/orkestrasi |
| Middleware shell (FastAPI): `/health`, `/activity`, WS, envelope, pagu, gerbang §6 | **Nadhilla** | jembatan; memanggil pustaka agen |
| Entrypoint streaming agen — `yield` `tool.call/tool.result/step/verdict`; mode chat/QA grounded; expose function-calling (`probe` + `recall_history` + `show_evidence`) | **Hamzah** (Agent) | `core/agent/` + pembungkus stream |
| Hosting always-on (BUKAN Vercel) + `SECTORS_API_KEY`/`ANTHROPIC_API_KEY`; `CreditAwareClient` termeter untuk middleware | **Melco** (Infra) | agen di middleware tetap lewat gateway termeter |

---

## 10. Keputusan untuk sign-off

1. **Setujui C6** (perluasan AD-1 dua-bidang) di `contracts/CHANGES.md`? Ini prasyarat semua di bawah.
2. **Kejar bidang live?** Kalau ya, Hamzah sanggup entrypoint stream sebelum ~24 Sep? Kalau ragu → **kirim Opsi 1 statis saja**, live hanya untuk video rekaman.
3. **Host middleware** siapa & di mana (Melco)? Endpoint `/health` publik untuk degrade.
4. **`v:1` dikunci?** Perubahan amplop/tipe event setelahnya menaikkan `v`, tidak menyentuh `schema_version` `contracts/`.

> Kalau tak ada yang di-live-kan sebelum freeze, dokumen ini tetap berguna sebagai
> **spesifikasi yang membuktikan arsitektur dipikirkan** — dan `AgentChat` statis sudah
> mengikuti bentuk `Answer` di §4, jadi jalur upgrade-nya nyata, bukan angan-angan.
