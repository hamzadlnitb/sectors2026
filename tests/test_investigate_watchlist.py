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


# ── jeda seleksi (B9) dan sinyal Tahap 1 ke perencana (D3) ──────────────────

KEMARIN = date(2026, 9, 10)


class _TranskripPalsu:
    """Cukup untuk `Memory.remember` — memori hanya membaca enam field."""

    symbol = "ASLI"
    as_of = KEMARIN
    pantau_score = 62
    band = "waspada"
    confidence = 0.92
    credits_total = 3


def _dua_hari(tmp_path, *, skor_kemarin: float, skor_hari_ini: float):
    """Watchlist untuk KEMARIN dan AS_OF dengan skor seleksi yang bisa diatur."""
    for hari, skor in ((KEMARIN, skor_kemarin), (AS_OF, skor_hari_ini)):
        d = tmp_path / hari.isoformat()
        d.mkdir(parents=True, exist_ok=True)
        (d / "watchlist.json").write_text(json.dumps({
            "as_of": hari.isoformat(),
            "candidates": [
                {"symbol": "ASLI", "score": skor,
                 "signals": {"volume_z": 12.7612, "return_5d": 0.2903,
                             "return_20d": 1.0202, "small_cap": 1.0, "peristiwa": 0.0},
                 "alasan": "volume 12.8σ di atas baseline"},
                {"symbol": "NICK", "score": 0.30, "signals": {}, "alasan": ""},
            ],
        }), encoding="utf-8")


def _memori_dengan_asli_kemarin(tmp_path):
    mem = Memory(tmp_path / "mem.duckdb")
    mem.remember(_TranskripPalsu(), None)
    return mem


def _kalender_tetap(monkeypatch):
    """Kalender bursa yang tidak bergantung pada isi warehouse nyata."""
    import tools.investigate_watchlist as m
    monkeypatch.setattr(m, "trading_days",
                        lambda wh, as_of, lookback: [date(2026, 9, 9), KEMARIN, AS_OF])


def test_kandidat_dilewati_bila_baru_diselidiki_dan_seleksi_tidak_bergerak(tmp_path, monkeypatch):
    _kalender_tetap(monkeypatch)
    _dua_hari(tmp_path, skor_kemarin=0.72, skor_hari_ini=0.73)

    hasil = run(AS_OF, memory=_memori_dengan_asli_kemarin(tmp_path), top=1,
                offline=True, runs_root=tmp_path)

    assert [d["symbol"] for d in hasil["diselidiki"]] == ["NICK"], \
        "kandidat berikutnya naik menggantikan yang dilewati"
    assert any(s.startswith("ASLI:") and "keyakinan 92%" in s for s in hasil["dilewati"])


def test_kandidat_tetap_diselidiki_bila_skor_seleksi_bergerak(tmp_path, monkeypatch):
    """Satu syarat meleset = ada yang berubah = investigasi jalan."""
    _kalender_tetap(monkeypatch)
    _dua_hari(tmp_path, skor_kemarin=0.50, skor_hari_ini=0.73)

    hasil = run(AS_OF, memory=_memori_dengan_asli_kemarin(tmp_path), top=1,
                offline=True, runs_root=tmp_path)

    assert [d["symbol"] for d in hasil["diselidiki"]] == ["ASLI"]


def test_kandidat_tetap_diselidiki_bila_investigasi_lama_sudah_usang(tmp_path, monkeypatch):
    import tools.investigate_watchlist as m
    # Kalender maju: 10-09 sudah di luar jendela JEDA_HARI_BURSA.
    monkeypatch.setattr(m, "trading_days",
                        lambda wh, as_of, lookback: [AS_OF])
    _dua_hari(tmp_path, skor_kemarin=0.72, skor_hari_ini=0.73)

    hasil = run(AS_OF, memory=_memori_dengan_asli_kemarin(tmp_path), top=1,
                offline=True, runs_root=tmp_path)

    assert [d["symbol"] for d in hasil["diselidiki"]] == ["ASLI"]


def test_sinyal_tahap_1_diteruskan_ke_perencana(tmp_path, monkeypatch):
    """D3 — perencana membaca dasar seleksi yang sama dengan yang memilih emiten."""
    import tools.investigate_watchlist as m

    terekam: dict = {}
    asli = m.investigate_symbol

    def rekam(symbol, **kw):
        terekam[symbol] = kw.get("signals")
        return asli(symbol, **kw)

    monkeypatch.setattr(m, "investigate_symbol", rekam)
    _dua_hari(tmp_path, skor_kemarin=0.72, skor_hari_ini=0.73)

    run(AS_OF, memory=Memory(tmp_path / "mem.duckdb"), top=1, offline=True,
        runs_root=tmp_path)

    sinyal = terekam["ASLI"]
    assert sinyal["volume_z"] == "12.8σ di atas baseline"
    assert sinyal["return_5_hari_bursa"] == "+29%"
    assert sinyal["kapitalisasi"] == "kecil"
    assert "peristiwa_korporasi" not in sinyal, "nilai nol bukan sinyal"
    assert sinyal["alasan_masuk_watchlist"].startswith("volume 12.8σ")
