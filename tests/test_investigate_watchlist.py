"""Cron Tahap 2 — driver investigasi watchlist. Nol jaringan, nol kredit (offline)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from core.agent.memory import Memory
from tools.investigate_watchlist import read_candidates, run

AS_OF = date(2026, 9, 11)


def _watchlist(runs_root, symbols):
    d = runs_root / AS_OF.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    (d / "watchlist.json").write_text(json.dumps({
        "as_of": AS_OF.isoformat(),
        "candidates": [{"symbol": s, "score": 1.0 - i * 0.1}
                       for i, s in enumerate(symbols)],
    }), encoding="utf-8")
    return d


def test_menyelidiki_top_n_saja(tmp_path):
    """Ambil N teratas berdasarkan skor, bukan semua kandidat."""
    _watchlist(tmp_path, ["ASLI", "NICK", "JAWA", "TRUK", "SCCO"])
    hasil = run(AS_OF, memory=Memory(tmp_path / 'mem.duckdb'), top=2, offline=True, runs_root=tmp_path)

    diselidiki = [d["symbol"] for d in hasil["diselidiki"]]
    assert diselidiki == ["ASLI", "NICK"], "hanya 2 teratas"
    assert hasil["kredit"] == 0, "offline tidak boleh membelanjakan kredit"


def test_transkrip_tersimpan_dan_valid(tmp_path):
    from contracts.schemas import InvestigationTranscript

    _watchlist(tmp_path, ["ASLI"])
    run(AS_OF, memory=Memory(tmp_path / 'mem.duckdb'), top=1, offline=True, runs_root=tmp_path)

    path = tmp_path / "investigations" / f"ASLI-{AS_OF.isoformat()}.json"
    assert path.exists()
    t = InvestigationTranscript.model_validate_json(path.read_text(encoding="utf-8"))
    assert t.symbol == "ASLI" and t.as_of == AS_OF


def test_idempoten_tidak_menimpa(tmp_path):
    """Cron yang diulang hari sama tidak membayar dua kali, tidak menimpa."""
    _watchlist(tmp_path, ["ASLI", "NICK"])
    run(AS_OF, memory=Memory(tmp_path / 'mem.duckdb'), top=2, offline=True, runs_root=tmp_path)
    kedua = run(AS_OF, memory=Memory(tmp_path / 'mem.duckdb'), top=2, offline=True, runs_root=tmp_path)

    assert kedua["diselidiki"] == []
    assert set(kedua["dilewati"]) == {"ASLI", "NICK"}


def test_watchlist_hilang_ditolak_jelas(tmp_path):
    with pytest.raises(FileNotFoundError, match="Tahap 1"):
        run(AS_OF, memory=Memory(tmp_path / 'mem.duckdb'), top=3, offline=True, runs_root=tmp_path)


def test_watchlist_kosong_bukan_kegagalan(tmp_path):
    _watchlist(tmp_path, [])
    hasil = run(AS_OF, memory=Memory(tmp_path / 'mem.duckdb'), top=3, offline=True, runs_root=tmp_path)
    assert hasil["diselidiki"] == [] and hasil["gagal"] == []


def test_kandidat_terurut_skor(tmp_path):
    _watchlist(tmp_path, ["ZZZZ", "AAAA"])  # ZZZZ skor lebih tinggi
    cand = read_candidates(AS_OF, tmp_path)
    assert [c["symbol"] for c in cand] == ["ZZZZ", "AAAA"]


def test_satu_gagal_tidak_menjatuhkan_batch(tmp_path, monkeypatch):
    """LLM ngambek di satu emiten tidak boleh menghentikan sisanya."""
    import tools.investigate_watchlist as m

    asli = m.investigate_symbol

    def kadang_gagal(symbol, **kw):
        if symbol == "NICK":
            raise RuntimeError("LLM timeout")
        return asli(symbol, **kw)

    monkeypatch.setattr(m, "investigate_symbol", kadang_gagal)
    _watchlist(tmp_path, ["ASLI", "NICK", "JAWA"])
    hasil = run(AS_OF, memory=Memory(tmp_path / 'mem.duckdb'), top=3, offline=True, runs_root=tmp_path)

    assert [d["symbol"] for d in hasil["diselidiki"]] == ["ASLI", "JAWA"]
    assert any("NICK" in g for g in hasil["gagal"])
