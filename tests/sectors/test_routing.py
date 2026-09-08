"""Tabel perutean: biaya diketahui sebelum panggilan, transport bukan urusan LLM."""

from __future__ import annotations

import json

import pytest

from core.sectors import routing
from core.sectors.errors import UnknownEndpoint


def test_sapuan_tier1_tetap_di_bawah_enam_kredit():
    """Target TASK_MELCO M1: sapuan market-wide ≤6 kredit/hari.

    250 kredit operasi harian dibagi 25 hari bursa = 10 kredit/hari untuk sapuan
    DAN investigasi agen. Kalau sapuan sendiri sudah 8, tidak ada sisa untuk agen.
    """
    total = sum(routing.cost_of(name) for name in routing.TIER1_SWEEP)
    assert total <= 6, f"sapuan Tier-1 naik jadi {total} kredit/hari"


def test_tiap_endpoint_punya_minimal_satu_transport():
    for ep in routing.endpoints():
        assert ep.transports, f"{ep.name} tidak bisa dipanggil lewat jalur mana pun"


def test_biaya_dalam_rentang_kontrak():
    """ToolCatalogEntry.credit_cost dipatok 0..3 di contracts/schemas.py."""
    for ep in routing.endpoints():
        assert 0 <= ep.credit_cost <= 3, f"{ep.name} biayanya {ep.credit_cost}"


def test_endpoint_tak_terdaftar_ditolak():
    with pytest.raises(UnknownEndpoint, match="routing.py"):
        routing.route("fetch-yang-dikarang-llm")


def test_transport_mengikuti_tabel_bukan_permintaan_bebas():
    # fetch-free-float hanya punya jalur MCP; minta REST tidak mengubah apa pun.
    assert routing.transport_for("fetch-free-float", prefer="rest") == "mcp"
    # fetch-close punya dua jalur. Sejak spike membuktikan jalur REST-nya
    # menjawab HTTP 400, tabel mengarahkannya ke MCP — bukti, bukan selera.
    assert routing.transport_for("fetch-close") == "mcp"
    assert routing.transport_for("fetch-close", prefer="rest") == "rest"


def test_fallback_hanya_untuk_endpoint_dua_jalur():
    assert routing.fallback_for("fetch-close", "rest") == "mcp"
    assert routing.fallback_for("fetch-free-float", "mcp") is None


def test_hasil_spike_menimpa_asumsi(tmp_path, monkeypatch):
    """Angka terukur menang atas tebakan — dan barisnya jadi 'terverifikasi'."""
    observed = tmp_path / "observed.json"
    observed.write_text(json.dumps({
        "endpoints": {"fetch-close": {"ok": True, "verified": True, "cost_measured": True,
                                      "credit_cost": 3, "rest_path": "/daily/close-all/"}}
    }), encoding="utf-8")
    monkeypatch.setattr(routing, "OBSERVED_PATH", observed)

    ep = routing.route("fetch-close")
    assert ep.credit_cost == 3
    assert ep.rest_path == "/daily/close-all/"
    assert ep.verified is True


def test_biaya_tidak_ditimpa_tanpa_pengukuran_sungguhan(tmp_path, monkeypatch):
    """Ledger mencatat biaya menurut TABEL INI, bukan tagihan API — Sectors tidak
    mengirim ongkos di respons. Membiarkan catatan itu menimpa balik tabelnya
    berarti mengukur asumsi dengan asumsi lalu menyebutnya terverifikasi."""
    observed = tmp_path / "observed.json"
    observed.write_text(json.dumps({"endpoints": {
        "fetch-suspensions": {"ok": True, "verified": True, "credit_cost": 99},
    }}), encoding="utf-8")
    monkeypatch.setattr(routing, "OBSERVED_PATH", observed)
    assert routing.route("fetch-suspensions").credit_cost == 1


def test_endpoint_gagal_tidak_dianggap_terukur(tmp_path, monkeypatch):
    """Spike mencatat kegagalan juga. Menandainya terukur akan membuat
    docs/endpoint-costs.md mengaku 'terukur' untuk endpoint yang menjawab 404."""
    observed = tmp_path / "observed.json"
    observed.write_text(json.dumps({"endpoints": {
        "fetch-close": {"ok": False, "verified": False, "credit_cost": 9,
                        "error": "HTTP 404"},
    }}), encoding="utf-8")
    monkeypatch.setattr(routing, "OBSERVED_PATH", observed)

    ep = routing.route("fetch-close")
    assert ep.verified is False
    assert ep.credit_cost == 1, "biaya dari panggilan yang gagal tidak boleh dipakai"


def test_observed_rusak_tidak_menjatuhkan_tabel(tmp_path, monkeypatch):
    rusak = tmp_path / "observed.json"
    rusak.write_text("{bukan json", encoding="utf-8")
    monkeypatch.setattr(routing, "OBSERVED_PATH", rusak)
    assert routing.route("fetch-close").credit_cost == 1
