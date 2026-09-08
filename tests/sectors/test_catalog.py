"""Katalog tool — yang membuat klaim 'innovative use of MCP' punya isi. [AD-7]

Yang membedakan "memakai MCP" dari "memakai MCP secara inovatif" adalah harga
kredit yang ikut disajikan ke perencana. Tes di sini menjaga bagian itu, bukan
jumlah tool yang dipanggil.
"""

from __future__ import annotations

import json

from core.sectors import catalog, routing


def test_katalog_perencana_jalan_tanpa_jaringan():
    """Hamzah punya katalog sejak hari pertama, bahkan kalau keputusan 11 Sep
    berakhir REST-only."""
    entri = catalog.for_planner()
    assert len(entri) == 6


def test_tiap_alat_membawa_harga():
    """Katalog tanpa harga cuma daftar nama, dan perencana tidak bisa memilih
    di bawah pagu."""
    for entry in catalog.for_planner():
        assert entry["credit_cost"] > 0
        assert entry["routes"]
        assert all(r["credit_cost"] > 0 for r in entry["routes"])


def test_katalog_terurut_dari_termurah():
    """Perencana membaca dari atas; yang murah harus terlihat lebih dulu."""
    biaya = [e["credit_cost"] for e in catalog.for_planner()]
    assert biaya == sorted(biaya)


def test_biaya_alat_sama_dengan_jumlah_endpointnya():
    """Ditulis di satu tempat saja. Kalau boleh berbeda, dua angka akan
    menyimpang dan perencana menganggarkan dari yang salah."""
    for entry in catalog.for_planner():
        assert entry["credit_cost"] == sum(r["credit_cost"] for r in entry["routes"])


def test_status_verifikasi_ikut_terbawa():
    """Perencana harus tahu mana biaya terukur dan mana yang masih tebakan.

    Sengaja tidak mematok angkanya: spike menambah endpoint terukur dari waktu
    ke waktu, dan tes yang mematok jumlah akan merah tiap kali spike jalan —
    lalu dilonggarkan orang, lalu berhenti berarti.
    """
    for entry in catalog.for_planner():
        assert isinstance(entry["cost_verified"], bool)
        # Alat dianggap terukur hanya kalau SELURUH endpoint di baliknya terukur.
        assert entry["cost_verified"] == all(r["verified"] for r in entry["routes"])


def test_katalog_statis_lolos_kontrak():
    for entry in catalog.static_catalog():
        assert entry.transport == "mcp"
        assert 0 <= entry.credit_cost <= 3
        assert entry.args_schema


def test_cakupan_jujur_saat_server_belum_ditarik():
    cov = catalog.coverage([])
    assert cov["available"] == 0
    assert cov["used"] > 0
    assert cov["missing_from_server"], "tanpa data server, semua dianggap belum terkonfirmasi"


def test_cakupan_menandai_tool_yang_tidak_ada_di_server():
    palsu = [{"name": "get_daily_close"}, {"name": "tool_yang_tidak_kita_pakai"}]
    cov = catalog.coverage(palsu)
    assert "get_daily_close" in cov["matched"]
    assert "tool_yang_tidak_kita_pakai" in cov["unused_on_server"]
    assert "get_free_float" in cov["missing_from_server"]


def test_dump_bolak_balik(tmp_path):
    tools = [{"name": "get_daily_close", "description": "x", "args_schema": {}}]
    path = catalog.save_dump(tools, tmp_path / "mcp.json")
    assert catalog.load_dump(path) == tools


def test_dump_rusak_tidak_menjatuhkan_katalog(tmp_path):
    rusak = tmp_path / "mcp.json"
    rusak.write_text("{bukan json", encoding="utf-8")
    assert catalog.load_dump(rusak) == []


def test_dump_membawa_stempel_waktu(tmp_path):
    path = catalog.save_dump([{"name": "a"}], tmp_path / "m.json")
    isi = json.loads(path.read_text(encoding="utf-8"))
    assert isi["fetched_at"] and isi["tool_count"] == 1


def test_rute_menyebut_transport_cadangan():
    """Fallback hanya untuk endpoint dua jalur — itu yang dijanjikan QA M5."""
    rute = {r.endpoint: r for r in catalog.routes_for(
        ("fetch-close", "fetch-free-float"))}
    assert rute["fetch-close"].alt_transport == "mcp"
    assert rute["fetch-free-float"].alt_transport is None


def test_setiap_endpoint_mcp_punya_nama_tool():
    for ep in routing.endpoints(transport="mcp"):
        assert ep.mcp_tool, f"{ep.name} dirutekan ke MCP tanpa nama tool"
