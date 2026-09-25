"""Jalur permintaan via GitHub Issue [AUDIT T3]. Nol jaringan: `gh` dipalsukan."""

from __future__ import annotations

import json
from datetime import date

import pytest

from core.agent.memory import Memory
from tools import permintaan as jalur
from tools.investigate_watchlist import run
from tools.vocab_guard import periksa_teks

AS_OF = date(2026, 9, 11)
SAH = {"ASLI", "NICK", "JAWA", "TRUK", "BBCA"}


def _issue(nomor, kode=None, judul=None):
    body = f"### Kode emiten\n\n{kode}\n" if kode is not None else ""
    return {"number": nomor, "title": judul or f"selidiki: {kode or ''}", "body": body}


class GhPalsu:
    def __init__(self, issues=None):
        self.issues = issues or []
        self.panggilan: list[list[str]] = []

    def __call__(self, args):
        self.panggilan.append(args)
        if args[:2] == ["issue", "list"]:
            return json.dumps(self.issues)
        return ""


# ── membaca issue ───────────────────────────────────────────────────────────
def test_kode_dari_field_template_dan_judul():
    assert jalur.kode_dari_issue(_issue(1, "bbca")) == "BBCA"
    assert jalur.kode_dari_issue({"title": "Selidiki: tlkm", "body": ""}) == "TLKM"
    assert jalur.kode_dari_issue({"title": "tolong dong", "body": "apa saja"}) is None


def test_issue_dibaca_urut_nomor():
    gh = GhPalsu([_issue(9, "NICK"), _issue(3, "ASLI")])
    assert [i["number"] for i in jalur.baca_issue(gh)] == [3, 9]
    assert gh.panggilan[0][:4] == ["issue", "list", "--label", "selidiki"]


# ── validasi: isi issue adalah data tak tepercaya ──────────────────────────
@pytest.mark.parametrize("isi", ["ZZZZ", "BBC", "BBCA; rm -rf /", "$(id)", "", "B B C A"])
def test_kode_tak_sah_ditolak_tanpa_menyimpan_isinya(isi):
    [p] = jalur.siapkan([_issue(5, isi)], [], SAH)
    assert p["status"] == "ditolak"
    assert p["symbol"] is None, "isi mentah tak sah tidak boleh ikut ke artefak ter-commit"


def test_jatah_per_malam_sisanya_ditunda():
    issues = [_issue(n, k) for n, k in enumerate(["ASLI", "NICK", "JAWA", "TRUK"], 1)]
    daftar = jalur.siapkan(issues, [], SAH, maks=3)
    assert [p["status"] for p in daftar] == ["diterima"] * 3 + ["ditunda"]
    assert jalur.diterima(daftar) == ["ASLI", "NICK", "JAWA"]


def test_emiten_sama_diminta_dua_kali_diselidiki_sekali():
    daftar = jalur.siapkan([_issue(1, "ASLI"), _issue(2, "asli")], ["ASLI"], SAH)
    assert jalur.diterima(daftar) == ["ASLI"]
    assert [p["status"] for p in daftar] == ["diterima"] * 3, "ketiganya terpenuhi bersama"


# ── antrean investigasi ─────────────────────────────────────────────────────
def _watchlist(runs_root, symbols):
    d = runs_root / AS_OF.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    (d / "watchlist.json").write_text(json.dumps({
        "as_of": AS_OF.isoformat(),
        "candidates": [{"symbol": s, "score": 1.0 - i * 0.1} for i, s in enumerate(symbols)],
    }), encoding="utf-8")


def test_permintaan_diselidiki_sebelum_watchlist(tmp_path):
    _watchlist(tmp_path, ["ASLI", "NICK"])
    hasil = run(AS_OF, memory=Memory(tmp_path / "m.duckdb"), top=2, offline=True,
                runs_root=tmp_path, permintaan=["TRUK"])

    assert [d["symbol"] for d in hasil["diselidiki"]] == ["TRUK", "ASLI", "NICK"]
    assert hasil["status"]["TRUK"] == "diselidiki"


def test_permintaan_tidak_kena_jeda_seleksi(tmp_path, monkeypatch):
    """Jeda B9 melewati kandidat yang baru diselidiki. Permintaan eksplisit tidak."""
    import tools.investigate_watchlist as m

    monkeypatch.setattr(m, "_alasan_jeda", lambda *a, **k: "baru diselidiki")
    _watchlist(tmp_path, ["ASLI"])
    hasil = run(AS_OF, memory=Memory(tmp_path / "m.duckdb"), top=1, offline=True,
                runs_root=tmp_path, permintaan=["NICK"])
    assert hasil["status"] == {"NICK": "diselidiki", "ASLI": "jeda"}


def test_permintaan_yang_juga_di_watchlist_tidak_diselidiki_dua_kali(tmp_path):
    _watchlist(tmp_path, ["ASLI", "NICK"])
    hasil = run(AS_OF, memory=Memory(tmp_path / "m.duckdb"), top=2, offline=True,
                runs_root=tmp_path, permintaan=["NICK"])
    assert [d["symbol"] for d in hasil["diselidiki"]] == ["NICK", "ASLI"]


# ── CLI cron: jalur yang benar-benar dijalankan daily.yml ───────────────────
@pytest.fixture
def cli(tmp_path, monkeypatch):
    """main() dengan run/warehouse/issue dipalsukan — nol jaringan, nol memori nyata."""
    import tools.investigate_watchlist as m

    _watchlist(tmp_path, ["ASLI"])
    dipanggil = {}

    def run_palsu(as_of, **kw):
        dipanggil.update(kw)
        status = {s: "diselidiki" for s in kw["permintaan"]} | {"ASLI": "diselidiki"}
        return {"diselidiki": [], "dilewati": [], "gagal": [], "kredit": 0, "status": status}

    monkeypatch.setattr(m, "run", run_palsu)
    monkeypatch.setattr(m, "Warehouse", lambda *a, **k: None)
    monkeypatch.setattr(jalur, "kode_sah", lambda wh: SAH)
    return m, dipanggil


def test_cli_menyimpan_permintaan_berstatus(cli, tmp_path, monkeypatch):
    m, dipanggil = cli
    monkeypatch.setattr(jalur, "baca_issue", lambda: [_issue(7, "NICK"), _issue(8, "ZZZZ")])

    kode = m.main(["--as-of", AS_OF.isoformat(), "--runs", str(tmp_path),
                   "--requests", "--symbols=bbca"])

    assert kode == 0
    assert dipanggil["permintaan"] == ["NICK", "BBCA"]
    simpan = json.loads((tmp_path / AS_OF.isoformat() / "permintaan.json").read_text("utf-8"))
    assert [(p["issue"], p["status"]) for p in simpan["permintaan"]] == \
        [(7, "diselidiki"), (8, "ditolak"), (None, "diselidiki")]


def test_cli_issue_tak_terbaca_tidak_menjatuhkan_tahap_2(cli, tmp_path, monkeypatch):
    """Token hilang atau API GitHub ngambek = malam tanpa permintaan, bukan
    malam tanpa investigasi."""
    m, dipanggil = cli

    def meledak():
        raise RuntimeError("gh: authentication required")

    monkeypatch.setattr(jalur, "baca_issue", meledak)
    assert m.main(["--as-of", AS_OF.isoformat(), "--runs", str(tmp_path), "--requests",
                   "--symbols="]) == 0
    assert dipanggil["permintaan"] == []


def test_cli_tanpa_permintaan_tidak_menulis_berkas(cli, tmp_path):
    m, _ = cli
    assert m.main(["--as-of", AS_OF.isoformat(), "--runs", str(tmp_path)]) == 0
    assert not (tmp_path / AS_OF.isoformat() / "permintaan.json").exists()


# ── penutupan, setelah commit terdorong ─────────────────────────────────────
def _simpan(tmp_path, daftar):
    return jalur.simpan(daftar, AS_OF, tmp_path)


def test_tutup_hanya_yang_terpenuhi(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "tim/pantau")
    _simpan(tmp_path, [
        {"symbol": "ASLI", "issue": 1, "status": "diselidiki"},
        {"symbol": "NICK", "issue": 2, "status": "sudah_ada"},
        {"symbol": None, "issue": 3, "status": "ditolak", "alasan": "x"},
        {"symbol": "JAWA", "issue": 4, "status": "ditunda"},
        {"symbol": "TRUK", "issue": 5, "status": "gagal"},
        {"symbol": "BBCA", "issue": None, "status": "diselidiki"},   # dari dispatch
    ])
    gh = GhPalsu()
    jalur.tutup(AS_OF, tmp_path, gh)

    ditutup = [a[2] for a in gh.panggilan if a[:2] == ["issue", "close"]]
    assert ditutup == ["1", "2", "3"], "tertunda & gagal tetap terbuka untuk malam berikutnya"
    komentar = gh.panggilan[0][gh.panggilan[0].index("--comment") + 1]
    assert "https://github.com/tim/pantau/blob/main/runs/investigations/ASLI-2026-09-11.json" \
        in komentar
    assert "not planned" in gh.panggilan[2]


def test_tanpa_berkas_permintaan_tidak_ada_yang_ditutup(tmp_path):
    gh = GhPalsu()
    assert jalur.tutup(AS_OF, tmp_path, gh) == []
    assert gh.panggilan == []


@pytest.mark.parametrize("teks", [jalur.komentar_selesai("ASLI", AS_OF), jalur.komentar_ditolak()])
def test_komentar_balasan_lolos_larangan_kosakata(teks):
    """Komentar adalah keluaran PANTAU yang dibaca publik. [K5]"""
    assert periksa_teks(teks) == []
