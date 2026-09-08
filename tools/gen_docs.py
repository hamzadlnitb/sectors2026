"""Bangkitkan docs/endpoint-costs.md dan docs/mcp-catalog.md.

Dokumen ini **dibangkitkan, tidak ditulis tangan**, karena isinya harus sama
persis dengan yang dipakai kode saat menganggarkan. Tabel biaya yang ditulis
tangan akan menyimpang dari `routing.py` dalam hitungan hari, dan perencana
Hamzah menganggarkan dari angka yang salah tanpa ada yang sadar.

    make docs
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.console import setup_console  # noqa: E402
from core.sectors import catalog, routing  # noqa: E402

DOCS = ROOT / "docs"

HEADER = (
    "<!-- DIBANGKITKAN oleh tools/gen_docs.py — jangan diedit tangan. "
    "Ubah core/sectors/routing.py lalu jalankan: make docs -->\n"
)


def _status(ep: routing.Endpoint) -> str:
    return "terukur" if ep.verified else "asumsi"


def _measured_at() -> str:
    """Kapan spike terakhir mengukur biaya. '—' kalau belum pernah."""
    import json

    if not routing.OBSERVED_PATH.exists():
        return "—"
    try:
        return json.loads(routing.OBSERVED_PATH.read_text(encoding="utf-8")).get(
            "measured_at", "waktu tidak tercatat")
    except (json.JSONDecodeError, OSError):
        return "waktu tidak tercatat"


def endpoint_costs() -> str:
    tabel = routing.table()
    terukur = sum(1 for e in tabel.values() if e.verified)

    out = [HEADER, "# Biaya kredit per endpoint Sectors", ""]
    out.append(
        "Sumber kebenaran: [`core/sectors/routing.py`](../core/sectors/routing.py). "
        "Perencana agen menganggarkan dari angka di tabel ini, jadi angka yang salah "
        "di sini berarti pagu investigasi yang salah.\n"
    )
    if terukur == 0:
        out.append(
            "> ⚠️ **Belum ada satu pun biaya yang terukur.** Seluruh kolom *kredit* di bawah "
            "masih **asumsi**. Jalankan `make spike` (butuh `SECTORS_API_KEY`) untuk "
            "mengukurnya; hasilnya masuk ke `spikes/observed.json` dan otomatis menimpa "
            "asumsi di sini. Jangan menganggarkan ketat di atas angka yang belum terukur.\n"
        )
    else:
        out.append(f"> {terukur} dari {len(tabel)} endpoint sudah diukur lewat `make spike` "
                   f"(`spikes/observed.json`, {_measured_at()}). Sisanya masih **asumsi** — "
                   f"lihat kolom *Status*.\n")

    for tier, judul in ((1, "Tier 1 — sapuan market-wide harian"),
                        (2, "Tier 2 — hanya lewat probe agen")):
        endpoints = routing.endpoints(tier=tier)
        total = sum(e.credit_cost for e in endpoints)
        out.append(f"## {judul}")
        if tier == 1:
            out.append(f"\nDijalankan cron tiap hari bursa. Total **{total} kredit/hari** "
                       f"(target ≤6 — dijaga `tests/sectors/test_routing.py`).\n")
        else:
            out.append("\nTidak pernah dipanggil terjadwal. Hanya keluar saat agen memutuskan "
                       "satu probe layak dibeli untuk satu saham.\n")
        out.append("| Endpoint | Kredit | Status | Transport | Cadangan | Untuk apa |")
        out.append("| --- | ---: | --- | --- | --- | --- |")
        for ep in endpoints:
            transport = routing.transport_for(ep.name)
            alt = routing.fallback_for(ep.name, transport) or "—"
            out.append(f"| `{ep.name}` | {ep.credit_cost} | {_status(ep)} | {transport} | "
                       f"{alt} | {ep.description} |")
        out.append("")

    out.append("## Biaya per probe")
    out.append("\nYang dilihat perencana. Biaya probe = jumlah biaya endpoint yang "
               "dibungkusnya, dihitung dari tabel di atas — bukan ditulis terpisah.\n")
    out.append("| Probe | Komponen | Kredit | Transport | Endpoint |")
    out.append("| --- | --- | ---: | --- | --- |")
    total_probe = 0
    for entry in catalog.for_planner():
        total_probe += entry["credit_cost"]
        endpoints = ", ".join(f"`{r['endpoint']}`" for r in entry["routes"])
        out.append(f"| `{entry['tool']}` | {entry['component']} | {entry['credit_cost']} | "
                   f"{'+'.join(entry['transports'])} | {endpoints} |")
    out.append(f"\n**Investigasi menyeluruh = {total_probe} kredit** — ini penyebut klaim "
               f"penghematan agen (Angka 2, `ARCHITECTURE.md` §6), dan harus tetap di bawah "
               f"pagar 25 kredit per investigasi `[AD-6]`.\n")

    out.append("## Anggaran fase")
    out.append("\nDitegakkan `CreditAwareClient`: panggilan yang menembus pagu **ditolak** "
               "dengan `BudgetExceeded`, bukan diperingatkan. `make credits` mencetak posisi "
               "terkini dari `data/credit_ledger.jsonl`.\n")
    from core.sectors.ledger import CAPS, PHASE_LABEL, TOTAL_CAP

    out.append("| Fase | Pagu |")
    out.append("| --- | ---: |")
    for phase, cap in CAPS.items():
        out.append(f"| {PHASE_LABEL[phase]} (`{phase}`) | {cap} |")
    out.append(f"| **Total** | **{TOTAL_CAP}** |")
    out.append("")
    return "\n".join(out)


def mcp_catalog() -> str:
    tools = catalog.load_dump()
    cov = catalog.coverage(tools)

    out = [HEADER, "# Katalog tool MCP Sectors", ""]
    out.append("Server: `https://sectors-mcp.supertype.ai/mcp` · transport Streamable HTTP · "
               "klien **tulis sendiri** di [`core/sectors/transport_mcp.py`]"
               "(../core/sectors/transport_mcp.py).\n")
    out.append("Kenapa kliennya ditulis sendiri dan bukan memakai klien jadi: klien jadi tidak "
               "bisa dicegat. Dengan klien sendiri, tiap tool call MCP melewati "
               "`CreditAwareClient` yang sama persis seperti REST — pagu diperiksa, ledger "
               "dicatat, cache dipakai. `[AD-7]`\n")

    if not tools:
        out.append("> ⚠️ **Katalog server belum pernah ditarik.** Butuh `SECTORS_API_KEY`; "
                   "jalankan `make mcp-catalog`. Tabel di bawah adalah tool MCP yang "
                   "**terdaftar di tabel perutean kita**, yaitu nama yang kita harapkan ada "
                   "di server — belum dikonfirmasi.\n")
    else:
        out.append(f"Ditarik dari server: **{cov['available']} tool**. Yang dipakai PANTAU: "
                   f"**{cov['used']}**.\n")
        if cov["missing_from_server"]:
            out.append("> ⚠️ Nama berikut ada di tabel perutean kita tapi **tidak ada di "
                       f"server**: {', '.join('`' + n + '`' for n in cov['missing_from_server'])}. "
                       "Perbaiki `routing.py` sebelum jalur MCP dipakai.\n")

    out.append("## Endpoint yang kami rutekan lewat MCP")
    out.append("\nPembagian transport ditentukan **tabel per-endpoint, bukan LLM**. Perencana "
               "memilih *alat*; tabel memilih *jalur*.\n")
    out.append("| Tool MCP | Endpoint kami | Kredit | Transport utama | Ada di server? |")
    out.append("| --- | --- | ---: | --- | --- |")
    tersedia = {t["name"] for t in tools}
    for ep in routing.endpoints(transport="mcp"):
        utama = routing.transport_for(ep.name)
        ada = "—" if not tools else ("ya" if ep.mcp_tool in tersedia else "**tidak**")
        out.append(f"| `{ep.mcp_tool}` | `{ep.name}` | {ep.credit_cost} | {utama} | {ada} |")
    out.append("")

    out.append("## MCP vs REST untuk endpoint yang sama")
    out.append("\nBiaya kreditnya sama — yang berbeda adalah ongkos rekayasa dan ketersediaan. "
               "Endpoint dua jalur otomatis punya fallback: MCP mati → REST, tanpa "
               "menjatuhkan pipeline (`tests/sectors/test_client.py`).\n")
    out.append("| Endpoint | REST | MCP | Dipakai | Alasan |")
    out.append("| --- | --- | --- | --- | --- |")
    for ep in routing.endpoints():
        rest = f"`{ep.rest_path}`" if ep.rest_path else "—"
        mcp = f"`{ep.mcp_tool}`" if ep.mcp_tool else "—"
        alasan = ("sapuan massal butuh panggilan presisi & batched"
                  if routing.transport_for(ep.name) == "rest"
                  else "ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan")
        out.append(f"| `{ep.name}` | {rest} | {mcp} | {routing.transport_for(ep.name)} | "
                   f"{alasan} |")
    out.append("")

    if cov["unused_on_server"]:
        out.append("## Tool server yang tidak kami pakai")
        out.append(f"\n{len(cov['unused_on_server'])} tool tersedia tapi tidak dipakai. "
                   "Dicantumkan dengan sengaja: memakai sedikit tool secara sadar lebih jujur "
                   "daripada mengaku memakai semuanya.\n")
        out.append("```")
        out.append("\n".join(cov["unused_on_server"]))
        out.append("```\n")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    setup_console()
    argparse.ArgumentParser(description="Bangkitkan dokumen biaya & katalog").parse_args(argv)
    DOCS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    for name, isi in (("endpoint-costs.md", endpoint_costs()),
                      ("mcp-catalog.md", mcp_catalog())):
        path = DOCS / name
        path.write_text(isi.rstrip() + f"\n\n---\n_Dibangkitkan {stamp} oleh `make docs`._\n",
                        encoding="utf-8")
        print(f"tulis {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
