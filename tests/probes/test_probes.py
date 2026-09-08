"""QA gerbang M2 — enam probe.

Empat baris QA di TASK_MELCO.md M2 diuji di sini:

    tiap probe jalan pada warehouse-mini tanpa jaringan  → test_semua_probe_jalan_tanpa_jaringan
    ticker baru IPO tidak crash                          → test_ipo_baru_menyerah_dengan_alasan
    ticker tersuspend tidak crash                        → test_ticker_tersuspend_tidak_crash
    data hilang → sub_score None + alasan                → test_data_hilang_bukan_nol_diam_diam
"""

from __future__ import annotations

import pytest

from contracts.schemas import PROBE_TO_COMPONENT, ProbeResult
from core.probes.base import Context
from core.probes.registry import PROBES, baseline_credits, catalog, cost_table

SEMUA = list(PROBES.values())
NAMA = [p.name for p in SEMUA]


# ── QA 1: jalan tanpa jaringan ──────────────────────────────────────────────
@pytest.mark.parametrize("probe", SEMUA, ids=NAMA)
@pytest.mark.parametrize("symbol", ["FIXA", "FIXB", "FIXC", "FIXD", "FIXE", "FIXF"])
def test_semua_probe_jalan_tanpa_jaringan(probe, symbol, ctx):
    """36 kombinasi. Nol kredit, nol koneksi — klien sengaja None."""
    hasil = probe.run(symbol, ctx)

    assert isinstance(hasil, ProbeResult)
    assert hasil.probe == probe.name
    assert hasil.credits_spent == 0, "warehouse sudah terisi; tidak ada yang perlu dibeli"
    if hasil.sub_score is not None:
        assert 0 <= hasil.sub_score <= 100
        assert hasil.evidence, "sub_score ada tapi tanpa bukti — buku bukti jadi bolong"
    else:
        assert hasil.unavailable_reason


def test_probe_tenang_mendekati_nol(ctx):
    """FIXA sengaja dibuat tanpa pola. Probe yang 'menemukan' sesuatu di sini
    berarti terlalu sensitif, dan seluruh papan waspada akan penuh alarm palsu."""
    for probe in SEMUA:
        hasil = probe.run("FIXA", ctx)
        if hasil.sub_score is not None:
            assert hasil.sub_score < 25, f"{probe.name} memberi {hasil.sub_score} pada ticker tenang"


def test_probe_membedakan_tenang_dari_waspada(ctx):
    """Kalau FIXC tidak keluar lebih tinggi dari FIXA, probe tidak mengukur apa pun."""
    for probe in SEMUA:
        tenang = probe.run("FIXA", ctx).sub_score
        keras = probe.run("FIXC", ctx).sub_score
        if tenang is None or keras is None:
            continue
        assert keras >= tenang, f"{probe.name}: FIXC ({keras}) tidak di atas FIXA ({tenang})"


# ── QA 2: IPO baru ──────────────────────────────────────────────────────────
def test_ipo_baru_menyerah_dengan_alasan(ctx):
    """FIXD listing 20 Agu 2026 — 12 hari bursa. Yang butuh baseline panjang
    WAJIB menyerah dengan alasan, bukan menghitung z-score dari 11 titik."""
    hasil = {p.name: p.run("FIXD", ctx) for p in SEMUA}

    for name in ("volume_anomaly", "price_fundamental"):
        r = hasil[name]
        assert r.sub_score is None, f"{name} memaksakan skor dari riwayat 12 hari"
        assert "hari" in r.unavailable_reason.lower()

    # Yang tidak butuh riwayat panjang tetap harus bekerja.
    assert hasil["free_float"].sub_score is not None


# ── QA 3: ticker tersuspend ─────────────────────────────────────────────────
def test_ticker_tersuspend_tidak_crash(ctx):
    """FIXE disuspend 1 Sep; data pasar berhenti 31 Agu, tiga hari sebelum as_of."""
    for probe in SEMUA:
        hasil = probe.run("FIXE", ctx)
        assert hasil.sub_score is not None or hasil.unavailable_reason


def test_suspensi_terbaca_probe_struktural(ctx):
    hasil = PROBES["structural"].run("FIXE", ctx)
    assert hasil.sub_score is not None and hasil.sub_score > 0
    ids = {e.id for e in hasil.evidence}
    assert "sss.prior_suspension" in ids


def test_alasan_suspensi_tidak_wajar_menambah_skor(ctx):
    """FIXC disuspend dengan alasan 'pergerakan harga di luar kebiasaan';
    FIXE dengan alasan keterbukaan informasi. Yang pertama harus lebih tinggi."""
    tidak_wajar = PROBES["structural"].run("FIXC", ctx)
    biasa = PROBES["structural"].run("FIXE", ctx)
    assert tidak_wajar.sub_score > biasa.sub_score
    assert "sss.suspension_unusual" in {e.id for e in tidak_wajar.evidence}


# ── QA 4: data hilang ───────────────────────────────────────────────────────
def test_data_hilang_bukan_nol_diam_diam(ctx):
    """FIXF ada di daily_close dan tidak ada di mana-mana lagi.

    Nol yang tidak dijelaskan akan mencemari skor komposit tanpa ada yang sadar.
    Kontrak memaksa alasan; tes ini memaksa alasannya berguna. [C1 #4]
    """
    for name in ("broker_concentration", "volume_anomaly", "free_float", "foreign_flow"):
        hasil = PROBES[name].run("FIXF", ctx)
        assert hasil.sub_score is None, f"{name} mengembalikan skor dari data yang tidak ada"
        assert hasil.unavailable_reason
        assert len(hasil.unavailable_reason) > 20, "alasan terlalu pendek untuk berguna"
        assert hasil.evidence == [], "probe tak tersedia tidak boleh membawa bukti"


def test_struktural_membedakan_bersih_dari_belum_diisi(ctx, mini, tmp_path):
    """Emiten tanpa peristiwa = skor 0 (temuan sah).
    Warehouse tanpa tabel peristiwa = unavailable (belum diisi)."""
    from core.ingest.warehouse import Warehouse

    bersih = PROBES["structural"].run("FIXF", ctx)
    assert bersih.sub_score == 0
    assert "sss.clean" in {e.id for e in bersih.evidence}

    kosong = Context(as_of=ctx.as_of, warehouse=Warehouse(tmp_path), budget_remaining=25)
    hasil = PROBES["structural"].run("FIXF", kosong)
    assert hasil.sub_score is None
    assert "belum diisi" in hasil.unavailable_reason


# ── bentuk kontrak ──────────────────────────────────────────────────────────
def test_probe_gagal_tidak_menjatuhkan_investigasi(ctx, monkeypatch):
    """Pagar AD-6: agen wajib bisa menyimpulkan dengan bukti yang sudah terkumpul."""
    probe = PROBES["volume_anomaly"]
    monkeypatch.setattr(type(probe), "_compute",
                        lambda self, s, c: (_ for _ in ()).throw(RuntimeError("meledak")))
    hasil = probe.run("FIXB", ctx)
    assert hasil.sub_score is None
    assert "RuntimeError" in hasil.unavailable_reason and "meledak" in hasil.unavailable_reason


def test_bukti_menunjuk_endpoint_dan_params_yang_benar(ctx):
    """Buku bukti harus bisa diklik balik ke endpoint + parameter + as_of. [T12]"""
    for probe in SEMUA:
        hasil = probe.run("FIXC", ctx)
        for bukti in hasil.evidence:
            assert bukti.probe == probe.name
            assert bukti.source_endpoint in probe.endpoints
            assert bukti.source_params
            assert bukti.as_of.tzinfo is not None, "as_of naif ditolak kontrak [C1 #7]"
            assert bukti.display


def test_id_bukti_unik_dalam_satu_probe(ctx):
    """ComponentScore.evidence_ids menunjuk id; id kembar bikin tautan UI salah."""
    for probe in SEMUA:
        for symbol in ("FIXA", "FIXB", "FIXC"):
            ids = [e.id for e in probe.run(symbol, ctx).evidence]
            assert len(ids) == len(set(ids)), f"{probe.name}/{symbol} punya id bukti kembar"


def test_prefiks_id_bukti_sesuai_komponen(ctx):
    for probe in SEMUA:
        prefiks = probe.component.lower()
        for bukti in probe.run("FIXB", ctx).evidence:
            assert bukti.id.startswith(f"{prefiks}."), f"{bukti.id} bukan milik {probe.component}"


# ── registry ────────────────────────────────────────────────────────────────
def test_enam_probe_menutup_enam_komponen():
    assert set(PROBES) == set(PROBE_TO_COMPONENT)
    assert {p.component for p in SEMUA} == set(PROBE_TO_COMPONENT.values())


def test_biaya_probe_sesuai_rentang_arsitektur():
    """ARCHITECTURE §3 mematok rentang per alat. Perencana menganggarkan dari sini."""
    rentang = {
        "broker_concentration": (2, 6), "volume_anomaly": (1, 3), "price_fundamental": (2, 5),
        "free_float": (1, 2), "foreign_flow": (2, 4), "structural": (2, 5),
    }
    for name, biaya in cost_table().items():
        low, high = rentang[name]
        assert low <= biaya <= high, f"{name} berbiaya {biaya}, di luar {low}–{high}"


def test_investigasi_menyeluruh_muat_di_pagar_agen():
    """Pagar 25 kredit per investigasi [AD-6]. Kalau keenam probe saja sudah
    melebihi, agen tidak akan pernah bisa dibandingkan dengan baseline
    menyeluruh — dan Angka 2 kehilangan penyebutnya."""
    assert baseline_credits() <= 25


def test_katalog_probe_lolos_kontrak():
    entri = catalog()
    assert len(entri) == 6
    for e in entri:
        assert e.name.startswith("probe_")
        assert 0 <= e.credit_cost <= 3, "ToolCatalogEntry mematok 0..3"
        assert len(e.description) > 60, "deskripsi terlalu pendek untuk dipakai perencana"
        assert e.args_schema["required"] == ["symbol"]
