"""Katalog tool — apa yang boleh dipilih perencana, berikut harganya. [AD-7]

Ini berkas yang membuat klaim "innovative use of MCP" punya isi. Yang membedakan
"memakai MCP" dari "memakai MCP secara inovatif" bukan jumlah tool yang
dipanggil, tapi bahwa **perencana melihat harga kredit tiap tool dan memilih di
bawah pagu anggaran**. Katalog tanpa harga cuma daftar nama.

Dua katalog, dua pembaca:

* `for_planner()` — enam probe (alat kita), dengan rincian transport dan biaya
  tiap endpoint yang dibungkusnya. Ini yang masuk prompt perencana Hamzah.
* `mcp_tools()` — katalog mentah dari server MCP, dipakai untuk membandingkan
  apa yang tersedia di sana dengan apa yang benar-benar kita pakai, dan untuk
  membuktikan kliennya memang tersambung. Butuh API key.

`for_planner()` **tidak butuh jaringan**: harganya dari tabel perutean. Jadi
Hamzah punya katalog sejak hari pertama, bahkan kalau keputusan 11 Sep berakhir
REST-only.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import ToolCatalogEntry  # noqa: E402
from core.sectors import routing  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DUMP_PATH = ROOT / "spikes" / "mcp-tools.json"


@dataclass
class ToolRoute:
    """Satu endpoint di balik satu probe: lewat mana, berapa, sudah terukur belum."""

    endpoint: str
    transport: str
    credit_cost: int
    verified: bool
    alt_transport: str | None


def routes_for(endpoints: tuple[str, ...]) -> list[ToolRoute]:
    out = []
    for name in endpoints:
        ep = routing.route(name)
        transport = routing.transport_for(name)
        out.append(ToolRoute(
            endpoint=name, transport=transport, credit_cost=ep.credit_cost,
            verified=ep.verified, alt_transport=routing.fallback_for(name, transport),
        ))
    return out


def for_planner() -> list[dict]:
    """Katalog yang disajikan ke perencana: alat, harga, dan jalurnya.

    Diimpor telat supaya core.sectors tidak bergantung pada core.probes —
    arahnya harus satu jalur saja, kalau tidak impor melingkar.
    """
    from core.probes.registry import DESCRIPTIONS, PROBES

    keluar = []
    for name, probe in PROBES.items():
        rute = routes_for(probe.endpoints)
        keluar.append({
            "tool": f"probe_{name}",
            "component": probe.component,
            "description": DESCRIPTIONS[name],
            "credit_cost": probe.cost_estimate("XXXX"),
            "args_schema": {"symbol": "^[A-Z]{4}$"},
            "routes": [asdict(r) for r in rute],
            "transports": sorted({r.transport for r in rute}),
            "cost_verified": all(r.verified for r in rute),
        })
    return sorted(keluar, key=lambda t: t["credit_cost"])


def static_catalog() -> list[ToolCatalogEntry]:
    """Endpoint MCP menurut tabel perutean — tanpa menyentuh server.

    Dipakai kalau MCP belum/tidak jadi dipakai: perencana tetap punya bentuk
    katalog yang sama, cuma isinya asumsi, dan `verified` mengatakannya.
    """
    return [
        ToolCatalogEntry(
            name=ep.mcp_tool or ep.name, transport="mcp", description=ep.description,
            args_schema=ep.args_schema, credit_cost=ep.credit_cost,
        )
        for ep in routing.endpoints(transport="mcp")
    ]


def mcp_tools(api_key: str | None = None, url: str | None = None) -> list[dict]:
    """Tarik katalog asli dari server MCP. Gratis — list_tools bukan tool call."""
    import os

    from core.sectors.transport_mcp import DEFAULT_MCP_URL, McpTransport

    key = api_key or os.environ.get("SECTORS_API_KEY")
    if not key:
        raise RuntimeError("SECTORS_API_KEY tidak diset — katalog MCP tidak bisa ditarik")

    transport = McpTransport(key, url or os.environ.get("SECTORS_MCP_URL") or DEFAULT_MCP_URL)
    try:
        return transport.list_tools()
    finally:
        transport.close()


def save_dump(tools: list[dict], path: Path | None = None) -> Path:
    """Simpan katalog mentah. Ini bukti klien MCP kita benar-benar tersambung."""
    path = path or DUMP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool_count": len(tools),
        "tools": tools,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_dump(path: Path | None = None) -> list[dict]:
    path = path or DUMP_PATH
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("tools", [])
    except (json.JSONDecodeError, OSError):
        return []


def coverage(tools: list[dict] | None = None) -> dict:
    """Berapa banyak tool MCP yang benar-benar kita pakai, dan mana yang belum.

    Angka ini masuk docs/mcp-catalog.md. Bukan untuk pamer cakupan — justru
    sebaliknya: memakai 8 dari 65 tool secara sadar lebih jujur daripada
    mengaku memakai semuanya.
    """
    tersedia = {t["name"] for t in (tools if tools is not None else load_dump())}
    dipakai = {ep.mcp_tool for ep in routing.endpoints(transport="mcp") if ep.mcp_tool}
    return {
        "available": len(tersedia),
        "used": len(dipakai),
        "matched": sorted(dipakai & tersedia) if tersedia else [],
        "missing_from_server": sorted(dipakai - tersedia) if tersedia else sorted(dipakai),
        "unused_on_server": sorted(tersedia - dipakai),
    }


def describe() -> str:
    lines = ["KATALOG UNTUK PERENCANA", ""]
    lines.append(f"{'tool':<28} {'komp':<5} {'kredit':>6}  transport")
    for entry in for_planner():
        tanda = "" if entry["cost_verified"] else "  (biaya asumsi)"
        lines.append(f"{entry['tool']:<28} {entry['component']:<5} {entry['credit_cost']:>6}  "
                     f"{'+'.join(entry['transports'])}{tanda}")
    cov = coverage()
    lines += ["", f"tool MCP terdaftar di tabel perutean: {cov['used']}"]
    if cov["available"]:
        lines.append(f"tool tersedia di server: {cov['available']}, cocok: {len(cov['matched'])}")
        if cov["missing_from_server"]:
            lines.append(f"⚠ tidak ada di server: {', '.join(cov['missing_from_server'])}")
    else:
        lines.append("katalog server belum pernah ditarik — jalankan make mcp-catalog")
    return "\n".join(lines)


if __name__ == "__main__":
    from core.console import setup_console

    setup_console()
    print(describe())
