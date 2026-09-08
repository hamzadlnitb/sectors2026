"""Tabel endpoint → transport → biaya kredit. Satu-satunya sumber kebenaran. [AD-7]

Dua hal yang dijaga berkas ini:

1. **Transport tidak pernah diputuskan LLM.** Perencana memilih *alat*; tabel di
   sini memilih *jalur*. Pembagiannya kini mengikuti **bukti**, bukan selera:
   tujuh endpoint yang terbukti menjawab lewat REST di spike 8 Sep tetap REST;
   yang REST-nya terbukti rusak (fetch-close 400, fetch-broker-summary-top 404)
   dan ekor panjang tool spesialis lewat MCP, yang katalognya sudah ditarik dan
   66 tool-nya terkonfirmasi ada.
2. **Biaya diketahui SEBELUM dipanggil.** Tanpa ini, perencana Hamzah tidak bisa
   menganggarkan dan CreditAwareClient tidak bisa menolak panggilan yang menembus
   pagu. Endpoint yang tidak terdaftar ditolak — lihat UnknownEndpoint.

**Dari mana biayanya.** Kolom credit_cost diambil dari **dokumentasi tool MCP
Sectors sendiri**, ditarik 8 Sep 2026 ke spikes/mcp-tools.json. Itu sumber yang
paling berwenang yang kita punya, dan beberapa di antaranya membatalkan asumsi
awal kami dengan selisih besar — lihat cost_note tiap baris.

⚠️  **Yang TIDAK bisa kami ukur sendiri.** Sectors tidak mengirim ongkos di
    respons, jadi ledger mencatat biaya menurut tabel ini, bukan tagihan
    sebenarnya. Spike hanya membuktikan endpoint MENJAWAB dan bentuk datanya
    apa — bukan berapa tagihannya. Karena itu load_observed() sengaja TIDAK
    menimpa credit_cost: menganggap catatan kita sendiri sebagai "pengukuran"
    berarti mengukur asumsi dengan asumsi, lalu menyebutnya terverifikasi.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from core.sectors.errors import UnknownEndpoint

Transport = Literal["rest", "mcp"]

ROOT = Path(__file__).resolve().parents[2]
OBSERVED_PATH = ROOT / "spikes" / "observed.json"


@dataclass(frozen=True)
class Endpoint:
    """Satu endpoint Sectors, apa pun transportnya."""

    name: str
    tier: int
    """1 = sapuan market-wide harian (murah, dijadwalkan). 2 = hanya lewat probe agen."""
    credit_cost: int
    """Biaya SATU unit tertagih, sesuai dokumentasi tool MCP."""
    preferred: Transport
    description: str
    args_schema: dict
    rest_path: str | None = None
    """Template jalur REST relatif terhadap base. Placeholder {x} diisi dari params."""
    mcp_tool: str | None = None
    verified: bool = False
    """True kalau spike F0 sudah benar-benar memanggilnya dan mencatat biayanya."""
    units: int = 1
    """Berapa unit tertagih yang dihabiskan SATU panggilan khas kita.

    Sectors tidak menagih per panggilan, tapi per unit: fetch-quarterly-financials
    1 kredit **per kuartal**, fetch-free-float 1 **per 100 emiten**, fetch-close 1
    **per halaman**. Menganggap semuanya 1 panggilan = 1 kredit membuat perencana
    salah anggar berlipat-lipat — dan itu ketahuan setelah kredit habis.
    """
    paginated: bool = False
    """Berbayar per halaman: biaya sebenarnya = jumlah halaman yang ditelusuri."""
    cost_note: str = ""

    @property
    def call_cost(self) -> int:
        """Biaya satu panggilan khas. Untuk endpoint berpaginasi ini biaya SATU
        halaman — totalnya ditentukan berapa halaman yang benar-benar ditarik."""
        return self.credit_cost * self.units

    @property
    def transports(self) -> tuple[Transport, ...]:
        out: list[Transport] = []
        if self.rest_path:
            out.append("rest")
        if self.mcp_tool:
            out.append("mcp")
        return tuple(out)

    def supports(self, transport: Transport) -> bool:
        return transport in self.transports


def _sym(extra: dict | None = None) -> dict:
    schema: dict = {
        "type": "object",
        "properties": {"symbol": {"type": "string", "pattern": "^[A-Z]{4}$"}},
        "required": ["symbol"],
    }
    if extra:
        schema["properties"].update(extra)
    return schema


_RANGE = {
    "start": {"type": "string", "format": "date"},
    "end": {"type": "string", "format": "date"},
}


# ── Tier 1 — sapuan market-wide harian, target ≤6 kredit/hari ────────────────
_TIER1 = [
    Endpoint(
        name="fetch-close", tier=1, verified=True, credit_cost=1, preferred="mcp",
        rest_path="/daily/close/", mcp_tool="fetch-close",
        paginated=True,
        cost_note="1 kredit PER HALAMAN, limit maks 30. Seluruh ~950 ticker = ~32 halaman "
                  "= ~32 kredit sekali tarik. Ini membatalkan asumsi '1 panggilan = semua ticker'.",
        description="Harga penutupan seluruh ticker IDX untuk satu tanggal bursa.",
        args_schema={"type": "object",
                     "properties": {"date": {"type": "string", "format": "date"}},
                     "required": ["date"]},
    ),
    Endpoint(
        name="fetch-most-traded-stocks", tier=1, verified=True, credit_cost=2, preferred="rest",
        rest_path="/most-traded/", mcp_tool="fetch-most-traded-stocks",
        description="Saham paling banyak diperdagangkan pada rentang tanggal.",
        args_schema={"type": "object",
                     "properties": {**_RANGE, "n_stock": {"type": "integer"}}},
    ),
    Endpoint(
        name="fetch-companies-top-changes", tier=1, verified=True, credit_cost=1, preferred="rest",
        rest_path="/companies/top-changes/", mcp_tool="fetch-companies-top-changes",
        cost_note="1 kredit per kombinasi klasifikasi x periode. Kita minta satu saja.",
        description="Emiten dengan perubahan harga/volume terbesar pada satu periode.",
        args_schema={"type": "object",
                     "properties": {"periods": {"type": "string"},
                                    "n_stock": {"type": "integer"}}},
    ),
    Endpoint(
        name="fetch-suspensions", tier=1, verified=True, credit_cost=1, preferred="rest",
        rest_path="/suspensions/", mcp_tool="fetch-suspensions",
        description="Riwayat suspensi IDX beserta alasan resminya. Sumber label kalibrasi.",
        args_schema={"type": "object",
                     "properties": {**_RANGE, "symbol": {"type": "string"}}},
    ),
    Endpoint(
        name="fetch-filings", tier=1, verified=True, credit_cost=1, preferred="rest",
        rest_path="/filings/", mcp_tool="fetch-filings",
        description="Filing transaksi insider (pemegang saham & pengurus).",
        args_schema={"type": "object",
                     "properties": {**_RANGE, "symbol": {"type": "string"},
                                    "transaction_type": {"type": "string"}}},
    ),
]

# ── Tier 2 — hanya dipanggil probe agen, per-ticker, berbayar lebih ──────────
_TIER2 = [
    Endpoint(
        name="fetch-daily-transaction", tier=2, verified=True, credit_cost=1, preferred="rest",
        rest_path="/daily/{symbol}/", mcp_tool="fetch-daily-transaction",
        cost_note="1 kredit untuk rentang sampai 90 hari. JAUH lebih murah daripada "
                  "fetch-close per hari kalau alam semestanya sudah dipersempit.",
        description="Harga, volume, dan kapitalisasi harian satu ticker pada rentang tanggal.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-broker-summary-top", tier=2, verified=True, credit_cost=2, preferred="mcp",
        rest_path="/broker-summary-top/{symbol}/", mcp_tool="fetch-broker-summary-top",
        description="Broker dengan net buy/sell terbesar pada satu ticker dan rentang tanggal.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-broker-summary", tier=2, verified=True, credit_cost=1, preferred="mcp",
        mcp_tool="fetch-broker-summary",
        description="Rincian net buy/sell per kode broker untuk satu ticker.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-foreign-flow", tier=2, verified=True, credit_cost=1, preferred="rest",
        rest_path="/foreign-flow/{symbol}/", mcp_tool="fetch-foreign-flow",
        description="Arus dana asing bersih harian pada satu ticker.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-free-float", tier=2, verified=True, credit_cost=1, preferred="mcp",
        mcp_tool="fetch-free-float",
        cost_note="1 kredit per 100 emiten. Tarikan market-wide praktis gratis.",
        description="Persentase saham beredar bebas (free float) per emiten.",
        args_schema=_sym(),
    ),
    Endpoint(
        name="fetch-company-report", tier=2, credit_cost=2, preferred="rest",
        rest_path="/company/report/{symbol}/", mcp_tool="fetch-company-report",
        description="Profil emiten: subsektor, kapitalisasi, tanggal listing, ikhtisar keuangan.",
        args_schema=_sym({"sections": {"type": "string"}}),
    ),
    Endpoint(
        name="fetch-quarterly-financials", tier=2, verified=True, credit_cost=1, units=5, preferred="mcp",
        mcp_tool="fetch-quarterly-financials",
        cost_note="1 kredit PER KUARTAL yang dikembalikan. Kita minta 5 (cukup untuk "
                  "perbandingan year-on-year), jadi 5 kredit per emiten.",
        description="Laporan keuangan kuartalan: pendapatan, laba bersih, total aset.",
        args_schema=_sym({"n_quarters": {"type": "integer"}}),
    ),
    Endpoint(
        name="fetch-corporate-actions", tier=2, verified=True, credit_cost=1, preferred="mcp",
        mcp_tool="fetch-corporate-actions",
        description="Aksi korporasi: rights issue, stock split, dividen, private placement.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-shareholders-composition", tier=2, verified=True, credit_cost=1, preferred="mcp",
        mcp_tool="fetch-shareholders-composition",
        description="Komposisi pemegang saham dan porsi kepemilikan asing.",
        args_schema=_sym(),
    ),
    Endpoint(
        name="fetch-companies-by-subsector", tier=2, credit_cost=1, preferred="mcp",
        mcp_tool="fetch-companies-by-subsector",
        description="Daftar emiten dalam satu subsektor. Dipakai membentuk himpunan kontrol "
                    "tersamakan saat kalibrasi.",
        args_schema={"type": "object",
                     "properties": {"sub_sector": {"type": "string"}},
                     "required": ["sub_sector"]},
    ),
]

_TABLE: dict[str, Endpoint] = {e.name: e for e in (*_TIER1, *_TIER2)}


def load_observed(path: Path | None = None) -> dict[str, dict]:
    """Biaya & jalur hasil pengukuran spike F0. Kosong kalau spike belum jalan."""
    path = path or OBSERVED_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    observed = payload.get("endpoints", {})
    return observed if isinstance(observed, dict) else {}


def _overlay(base: dict[str, Endpoint], observed: dict[str, dict]) -> dict[str, Endpoint]:
    """Angka terukur menang atas asumsi. Yang tidak terukur tetap ditandai belum verified.

    Kehadiran nama di spikes/observed.json TIDAK berarti terukur: spike juga
    mencatat endpoint yang GAGAL, lengkap dengan sebabnya. Menandai semuanya
    verified akan membuat docs/endpoint-costs.md mengaku "terukur" untuk
    endpoint yang sebenarnya menjawab HTTP 404 — persis kebohongan yang seluruh
    mekanisme ini dibuat untuk mencegahnya. Yang menentukan flag verified milik
    entri itu sendiri.
    """
    out = dict(base)
    for name, obs in observed.items():
        current = out.get(name)
        if current is None or not isinstance(obs, dict):
            continue
        merespons = bool(obs.get("ok"))
        patch: dict = {"verified": current.verified and merespons or merespons}
        # credit_cost hanya boleh ditimpa oleh pengukuran SUNGGUHAN, yang menandai
        # dirinya cost_measured. Spike biasa tidak bisa mengukur ongkos — ia cuma
        # mencatat ulang angka dari tabel ini, dan menimpakannya kembali ke sini
        # berarti mengukur asumsi dengan asumsi.
        if obs.get("cost_measured") and isinstance(obs.get("credit_cost"), int):
            patch["credit_cost"] = obs["credit_cost"]
        if merespons and obs.get("rest_path"):
            patch["rest_path"] = obs["rest_path"]
        out[name] = replace(current, **patch)
    return out


def table() -> dict[str, Endpoint]:
    """Tabel efektif: asumsi ditimpa hasil spike kalau ada."""
    return _overlay(_TABLE, load_observed())


def route(name: str) -> Endpoint:
    """Endpoint terdaftar, atau UnknownEndpoint. Tidak ada jalur diam-diam."""
    try:
        return table()[name]
    except KeyError:
        raise UnknownEndpoint(name) from None


def cost_of(name: str) -> int:
    """Biaya satu panggilan khas, sudah termasuk pengali unit."""
    return route(name).call_cost


def transport_for(name: str, prefer: Transport | None = None) -> Transport:
    """Transport yang dipakai untuk endpoint ini.

    Argumen prefer hanya boleh datang dari kode kita (mis. fallback saat MCP
    mati), tidak pernah dari keluaran LLM.
    """
    ep = route(name)
    if prefer and ep.supports(prefer):
        return prefer
    return ep.preferred if ep.supports(ep.preferred) else ep.transports[0]


def fallback_for(name: str, failed: Transport) -> Transport | None:
    """Transport cadangan kalau failed mati. None kalau endpoint cuma satu jalur."""
    others = [t for t in route(name).transports if t != failed]
    return others[0] if others else None


def endpoints(tier: int | None = None, transport: Transport | None = None) -> list[Endpoint]:
    out = sorted(table().values(), key=lambda e: (e.tier, e.name))
    if tier is not None:
        out = [e for e in out if e.tier == tier]
    if transport is not None:
        out = [e for e in out if e.supports(transport)]
    return out


# fetch-close SENGAJA tidak ikut sapuan harian meski ber-tier 1. Katalog MCP
# menyatakan ia berbayar 1 kredit per halaman dan seluruh ~950 ticker butuh ~32
# halaman: 32 kredit/hari x 25 hari bursa = 800 kredit, sementara seluruh pagu
# operasi harian cuma 250. Riwayat harga per emiten diambil jauh lebih murah
# lewat fetch-daily-transaction (1 kredit untuk rentang 90 hari) setelah alam
# semesta dipersempit. Ia tetap terdaftar karena backfill dan probe boleh
# memanggilnya sesekali dengan sadar.
TIER1_SWEEP: tuple[str, ...] = tuple(
    e.name for e in _TIER1 if e.name != "fetch-close"
)
"""Sapuan harian. Biayanya harus tetap ≤6 kredit — dijaga tes."""
