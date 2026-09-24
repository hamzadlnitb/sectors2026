"""Ledger kredit: pagu, alarm, dan ketahanan berkas."""

from __future__ import annotations

import pytest

from core.sectors.errors import BudgetExceeded
from core.sectors.ledger import CAPS, TOTAL_CAP, CreditLedger, report


def test_pagu_total_persis_seribu():
    """Jatah hackathon 1.000 kredit. Kalau tabel fase digeser tanpa sadar,
    tes ini yang meneriakkannya."""
    assert TOTAL_CAP == 1000
    assert CAPS == {"dev": 120, "backfill": 400, "eval": 130, "daily": 250, "reserve": 100}


def test_posisi_dihitung_ulang_dari_berkas(tmp_path):
    """Bukan dari variabel di memori — proses yang mati tidak menghilangkan catatan."""
    path = tmp_path / "l.jsonl"
    a = CreditLedger(path)
    a.record(phase="dev", endpoint="fetch-close", transport="rest", credits=3, params_hash="x")

    b = CreditLedger(path)
    assert b.spent("dev") == 3
    assert b.remaining("dev") == 117


def test_check_menolak_sebelum_belanja(tmp_path):
    ledger = CreditLedger(tmp_path / "l.jsonl", caps={"dev": 5})
    ledger.record(phase="dev", endpoint="e", transport="rest", credits=4, params_hash="x")
    ledger.check("dev", 1)
    with pytest.raises(BudgetExceeded) as err:
        ledger.check("dev", 2)
    assert err.value.spent == 4 and err.value.cap == 5


def test_fase_tak_dikenal_ditolak(tmp_path):
    ledger = CreditLedger(tmp_path / "l.jsonl")
    with pytest.raises(BudgetExceeded):
        ledger.check("fase-karangan", 1)


def test_cadangan_terkunci_secara_bawaan(tmp_path):
    ledger = CreditLedger(tmp_path / "l.jsonl")
    with pytest.raises(BudgetExceeded):
        ledger.check("reserve", 1)
    ledger.check("reserve", 1, allow_reserve=True)


def test_baris_rusak_tidak_menghapus_posisi(tmp_path):
    """Satu baris korup tidak boleh membuat seluruh posisi kredit hilang —
    kalau hilang, pagu jadi longgar tepat saat paling berbahaya."""
    path = tmp_path / "l.jsonl"
    ledger = CreditLedger(path)
    ledger.record(phase="dev", endpoint="e", transport="rest", credits=2, params_hash="x")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{bukan json\n")
    ledger.record(phase="dev", endpoint="e", transport="rest", credits=3, params_hash="y")

    assert ledger.spent("dev") == 5


def test_alarm_menyala_sekali_per_ambang(tmp_path, capsys):
    ledger = CreditLedger(tmp_path / "l.jsonl", caps={"dev": 10})
    for _ in range(7):
        ledger.record(phase="dev", endpoint="e", transport="rest", credits=1, params_hash="x")
    keluaran = capsys.readouterr().out
    assert "ALARM 70%" in keluaran
    assert keluaran.count("ALARM 70%") == 1

    for _ in range(2):
        ledger.record(phase="dev", endpoint="e", transport="rest", credits=1, params_hash="x")
    assert "ALARM 90%" in capsys.readouterr().out


def test_laporan_bisa_dibaca_saat_kosong(tmp_path):
    teks = report(CreditLedger(tmp_path / "kosong.jsonl"))
    assert "belum ada belanja tercatat" in teks
    assert "TOTAL" in teks


def test_laporan_merinci_per_endpoint(tmp_path):
    ledger = CreditLedger(tmp_path / "l.jsonl")
    ledger.record(phase="daily", endpoint="fetch-close", transport="rest", credits=1,
                  params_hash="x")
    ledger.record(phase="daily", endpoint="fetch-filings", transport="mcp", credits=2,
                  params_hash="y")
    teks = report(ledger)
    assert "fetch-filings" in teks and "3" in teks
    assert "2 panggilan berbayar" in teks


# ── laporan pemakaian LLM (AUDIT T4) ────────────────────────────────────────

def _llm_ledger(tmp_path, *baris):
    import json as _json
    p = tmp_path / "llm_ledger.jsonl"
    p.write_text("\n".join(_json.dumps(b) for b in baris) + "\n", encoding="utf-8")
    return p


def test_laporan_llm_mengelompokkan_per_penyedia_dan_model(tmp_path):
    """Datanya sudah dicatat sejak 10 Sep tapi tidak pernah ada pembacanya."""
    from core.sectors.ledger import laporan_llm

    berkas = _llm_ledger(
        tmp_path,
        {"provider": "claude", "model": "claude-sonnet-5",
         "input_tokens": 1000, "output_tokens": 200, "seconds": 3.0},
        {"provider": "claude", "model": "claude-sonnet-5",
         "input_tokens": 500, "output_tokens": 100, "seconds": 2.0},
        {"provider": "minimax", "model": "MiniMax-M3",
         "input_tokens": 300, "output_tokens": 50, "seconds": 1.0},
    )
    teks = laporan_llm(berkas)

    assert "claude/claude-sonnet-5" in teks and "minimax/MiniMax-M3" in teks
    assert "1.500" in teks, "token masuk claude dijumlahkan, dengan pemisah ribuan"
    assert "TOTAL" in teks and "3" in teks


def test_laporan_llm_kosong_bukan_kegagalan(tmp_path):
    """`make credits` tidak boleh merah cuma karena LLM belum pernah dipakai."""
    from core.sectors.ledger import laporan_llm

    assert laporan_llm(tmp_path / "tidak-ada.jsonl") == ""
    assert laporan_llm(_llm_ledger(tmp_path)) == ""


def test_laporan_llm_menelan_baris_rusak(tmp_path):
    """Ledger ditulis sambil jalan; baris separuh tidak boleh menjatuhkan laporan."""
    from core.sectors.ledger import laporan_llm

    p = tmp_path / "llm_ledger.jsonl"
    p.write_text('{"provider": "claude", "model": "x", "input_tokens": 7}\n{"pro',
                 encoding="utf-8")

    teks = laporan_llm(p)
    assert "claude/x" in teks, "baris yang sah tetap dilaporkan"
