"""Tabel endpoint → transport → biaya kredit. Satu-satunya sumber kebenaran. [AD-7]

Dua hal yang dijaga berkas ini:

1. **Transport tidak pernah diputuskan LLM.** Perencana memilih *alat*; tabel di
   sini memilih *jalur*. Sapuan massal lewat REST karena butuh panggilan presisi
   dan batched; ekor panjang tool spesialis lewat MCP karena 65+ tool sudah siap
   pakai dan tidak perlu 65 wrapper REST tulisan tangan.
2. **Biaya diketahui SEBELUM dipanggil.** Tanpa ini, perencana Hamzah tidak bisa
   menganggarkan dan CreditAwareClient tidak bisa menolak panggilan yang menembus
   pagu. Endpoint yang tidak terdaftar ditolak — lihat UnknownEndpoint.

⚠️  **Status verifikasi.** Kolom credit_cost dan rest_path di tabel bawah adalah
    **asumsi awal**, bukan hasil pengukuran. Spike F0 ("make spike", butuh API key)
    memanggil tiap endpoint sekali, mencatat biaya aktual ke spikes/observed.json,
    dan nilai itu **menimpa** asumsi di sini lewat load_observed(). Selama berkas
    itu belum ada, docs/endpoint-costs.md menandai barisnya "asumsi" — supaya tidak
    ada yang menganggarkan di atas angka karangan.
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
    preferred: Transport
    description: str
    args_schema: dict
    rest_path: str | None = None
    """Template jalur REST relatif terhadap base. Placeholder {x} diisi dari params."""
    mcp_tool: str | None = None
    verified: bool = False
    """True kalau spike F0 sudah benar-benar memanggilnya dan mencatat biayanya."""

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
        name="fetch-close", tier=1, credit_cost=1, preferred="rest",
        rest_path="/daily/close/", mcp_tool="get_daily_close",
        description="Harga penutupan seluruh ticker IDX untuk satu tanggal bursa.",
        args_schema={"type": "object",
                     "properties": {"date": {"type": "string", "format": "date"}},
                     "required": ["date"]},
    ),
    Endpoint(
        name="fetch-most-traded-stocks", tier=1, credit_cost=1, preferred="rest",
        rest_path="/most-traded/", mcp_tool="get_most_traded_stocks",
        description="Saham paling banyak diperdagangkan pada rentang tanggal.",
        args_schema={"type": "object",
                     "properties": {**_RANGE, "n_stock": {"type": "integer"}}},
    ),
    Endpoint(
        name="fetch-companies-top-changes", tier=1, credit_cost=1, preferred="rest",
        rest_path="/companies/top-changes/", mcp_tool="get_top_companies_movers",
        description="Emiten dengan perubahan harga/volume terbesar pada satu periode.",
        args_schema={"type": "object",
                     "properties": {"periods": {"type": "string"},
                                    "n_stock": {"type": "integer"}}},
    ),
    Endpoint(
        name="fetch-suspensions", tier=1, credit_cost=1, preferred="rest",
        rest_path="/suspensions/", mcp_tool="get_suspended_stocks",
        description="Riwayat suspensi IDX beserta alasan resminya. Sumber label kalibrasi.",
        args_schema={"type": "object",
                     "properties": {**_RANGE, "symbol": {"type": "string"}}},
    ),
    Endpoint(
        name="fetch-filings", tier=1, credit_cost=1, preferred="rest",
        rest_path="/filings/", mcp_tool="get_insider_trading_filings",
        description="Filing transaksi insider (pemegang saham & pengurus).",
        args_schema={"type": "object",
                     "properties": {**_RANGE, "symbol": {"type": "string"},
                                    "transaction_type": {"type": "string"}}},
    ),
]

# ── Tier 2 — hanya dipanggil probe agen, per-ticker, berbayar lebih ──────────
_TIER2 = [
    Endpoint(
        name="fetch-daily-transaction", tier=2, credit_cost=1, preferred="rest",
        rest_path="/daily/{symbol}/", mcp_tool="get_daily_transaction",
        description="Harga, volume, dan kapitalisasi harian satu ticker pada rentang tanggal.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-broker-summary-top", tier=2, credit_cost=3, preferred="rest",
        rest_path="/broker-summary-top/{symbol}/", mcp_tool="get_top_brokers",
        description="Broker dengan net buy/sell terbesar pada satu ticker dan rentang tanggal.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-broker-summary", tier=2, credit_cost=2, preferred="mcp",
        mcp_tool="get_broker_summary",
        description="Rincian net buy/sell per kode broker untuk satu ticker.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-foreign-flow", tier=2, credit_cost=2, preferred="rest",
        rest_path="/foreign-flow/{symbol}/", mcp_tool="get_foreign_flow",
        description="Arus dana asing bersih harian pada satu ticker.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-free-float", tier=2, credit_cost=1, preferred="mcp",
        mcp_tool="get_free_float",
        description="Persentase saham beredar bebas (free float) per emiten.",
        args_schema=_sym(),
    ),
    Endpoint(
        name="fetch-company-report", tier=2, credit_cost=2, preferred="rest",
        rest_path="/company/report/{symbol}/", mcp_tool="get_company_report",
        description="Profil emiten: subsektor, kapitalisasi, tanggal listing, ikhtisar keuangan.",
        args_schema=_sym({"sections": {"type": "string"}}),
    ),
    Endpoint(
        name="fetch-quarterly-financials", tier=2, credit_cost=2, preferred="mcp",
        mcp_tool="get_quarterly_financials",
        description="Laporan keuangan kuartalan: pendapatan, laba bersih, total aset.",
        args_schema=_sym({"n_quarters": {"type": "integer"}}),
    ),
    Endpoint(
        name="fetch-corporate-actions", tier=2, credit_cost=2, preferred="mcp",
        mcp_tool="get_corporate_actions",
        description="Aksi korporasi: rights issue, stock split, dividen, private placement.",
        args_schema=_sym(_RANGE),
    ),
    Endpoint(
        name="fetch-shareholders-composition", tier=2, credit_cost=2, preferred="mcp",
        mcp_tool="get_shareholders",
        description="Komposisi pemegang saham dan porsi kepemilikan asing.",
        args_schema=_sym(),
    ),
    Endpoint(
        name="fetch-companies-by-subsector", tier=2, credit_cost=1, preferred="mcp",
        mcp_tool="get_companies_by_subsector",
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
    """Angka terukur menang atas asumsi. Yang tidak terukur tetap ditandai belum verified."""
    out = dict(base)
    for name, obs in observed.items():
        current = out.get(name)
        if current is None or not isinstance(obs, dict):
            continue
        patch: dict = {"verified": True}
        if isinstance(obs.get("credit_cost"), int):
            patch["credit_cost"] = obs["credit_cost"]
        if obs.get("rest_path"):
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
    return route(name).credit_cost


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


TIER1_SWEEP: tuple[str, ...] = tuple(e.name for e in _TIER1)
"""Sapuan harian. Biayanya harus tetap ≤6 kredit — dijaga tes."""
