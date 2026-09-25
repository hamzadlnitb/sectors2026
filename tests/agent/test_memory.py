"""Memori harus mengingat APA yang sudah dilihat, bukan cuma bahwa ia melihat.

Tes ini menjaga D4 dari AUDIT.md: `transcript_path` sudah lama disimpan tapi
tidak pernah dibaca, sehingga perencana diminta "fokus pada apa yang berubah"
tanpa tahu komponen mana yang kemarin sudah 100/100 dan mana yang belum pernah
dijalankan. Akibat terukurnya: `free_float` — angka kuartalan — dibeli ulang
hampir tiap hari.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from core.agent.memory import Memory


@dataclass
class TranskripPalsu:
    symbol: str
    as_of: date
    pantau_score: int
    band: str
    confidence: float
    credits_total: int


def _transkrip_json(tmp_path, *, ffs_as_of: str, vas_as_of: str,
                    ffs_bukti_kedua: str | None = None):
    isi = {
        "symbol": "ASLI",
        "as_of": "2026-09-22",
        "components": [
            {"code": "BCI", "sub_score": None, "evidence_ids": []},
            {"code": "VAS", "sub_score": 100.0, "evidence_ids": ["vas.zscore"]},
            {"code": "PFD", "sub_score": None, "evidence_ids": []},
            {"code": "FFS", "sub_score": 28.0,
             "evidence_ids": ["ffs.pct", "ffs.data_age_days"]},
            {"code": "FRD", "sub_score": None, "evidence_ids": []},
            {"code": "SSS", "sub_score": None, "evidence_ids": []},
        ],
        "evidence": [
            {"id": "vas.zscore", "as_of": f"{vas_as_of}T16:00:00+07:00"},
            {"id": "ffs.pct", "as_of": f"{ffs_as_of}T16:00:00+07:00"},
            {"id": "ffs.data_age_days",
             "as_of": f"{ffs_bukti_kedua or ffs_as_of}T16:00:00+07:00"},
        ],
    }
    berkas = tmp_path / "ASLI-2026-09-22.json"
    berkas.write_text(json.dumps(isi), encoding="utf-8")
    return berkas


def _ingat(tmp_path, berkas):
    mem = Memory(path=tmp_path / "memory.duckdb")
    mem.remember(
        TranskripPalsu(symbol="ASLI", as_of=date(2026, 9, 22), pantau_score=62,
                       band="waspada", confidence=0.73, credits_total=3),
        berkas,
    )
    return mem


def test_briefing_menyebut_sub_skor_dan_umur_bukti(tmp_path):
    # ffs.pct per 07-09, ffs.data_age_days per 05-09: yang menentukan umur
    # komponen adalah bukti PALING BASI, bukan yang paling baru.
    berkas = _transkrip_json(tmp_path, ffs_as_of="2026-09-07", vas_as_of="2026-09-22",
                             ffs_bukti_kedua="2026-09-05")
    ingat = _ingat(tmp_path, berkas).recall("ASLI", before=date(2026, 9, 23))
    assert ingat is not None

    teks = ingat.briefing(date(2026, 9, 23))
    assert "VAS 100 (bukti per 22-09)" in teks
    # 05-09, bukan 07-09: bukti tertua yang dipakai.
    assert "FFS 28 (bukti per 05-09)" in teks
    assert "BCI/PFD/FRD/SSS belum pernah diperiksa" in teks


def test_bukti_lambat_berubah_yang_masih_segar_ditandai_jangan_dibeli_ulang(tmp_path):
    berkas = _transkrip_json(tmp_path, ffs_as_of="2026-09-20", vas_as_of="2026-09-22")
    ingat = _ingat(tmp_path, berkas).recall("ASLI", before=date(2026, 9, 23))

    teks = ingat.briefing(date(2026, 9, 23))
    assert "tidak perlu dibeli ulang" in teks
    assert "FFS" in teks.split("tidak perlu dibeli ulang")[1]


def test_bukti_lambat_berubah_yang_sudah_basi_tidak_ditandai_segar(tmp_path):
    # FFS berumur 18 hari > batas 15 → harus dibeli ulang, jadi tidak disebut.
    berkas = _transkrip_json(tmp_path, ffs_as_of="2026-09-05", vas_as_of="2026-09-22")
    ingat = _ingat(tmp_path, berkas).recall("ASLI", before=date(2026, 9, 23))

    assert "tidak perlu dibeli ulang" not in ingat.briefing(date(2026, 9, 23))


def test_transkrip_hilang_tidak_menjatuhkan_memori(tmp_path):
    """Memori dari mesin lain, atau `runs/` yang sudah dipangkas."""
    mem = _ingat(tmp_path, tmp_path / "tidak-ada.json")
    ingat = mem.recall("ASLI", before=date(2026, 9, 23))

    assert ingat is not None and ingat.components == {}
    teks = ingat.briefing(date(2026, 9, 23))
    assert "skor 62 (waspada)" in teks
    assert "APA YANG BERUBAH" in teks
