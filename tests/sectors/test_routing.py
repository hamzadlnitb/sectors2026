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
    # fetch-close punya dua jalur; kode kita boleh memilih.
    assert routing.transport_for("fetch-close") == "rest"
    assert routing.transport_for("fetch-close", prefer="mcp") == "mcp"


def test_fallback_hanya_untuk_endpoint_dua_jalur():
    assert routing.fallback_for("fetch-close", "rest") == "mcp"
    assert routing.fallback_for("fetch-free-float", "mcp") is None


def test_hasil_spike_menimpa_asumsi(tmp_path, monkeypatch):
    """Angka terukur menang atas tebakan — dan barisnya jadi 'terverifikasi'."""
    observed = tmp_path / "observed.json"
    observed.write_text(json.dumps({
        "endpoints": {"fetch-close": {"credit_cost": 3, "rest_path": "/daily/close-all/"}}
    }), encoding="utf-8")
    monkeypatch.setattr(routing, "OBSERVED_PATH", observed)

    ep = routing.route("fetch-close")
    assert ep.credit_cost == 3
    assert ep.rest_path == "/daily/close-all/"
    assert ep.verified is True
    # Yang tidak diukur tetap ditandai belum terverifikasi.
    assert routing.route("fetch-filings").verified is False


def test_observed_rusak_tidak_menjatuhkan_tabel(tmp_path, monkeypatch):
    rusak = tmp_path / "observed.json"
    rusak.write_text("{bukan json", encoding="utf-8")
    monkeypatch.setattr(routing, "OBSERVED_PATH", rusak)
    assert routing.route("fetch-close").credit_cost == 1
