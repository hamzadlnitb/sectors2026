"""Metrik Angka 2: yang diklaim laporan harus benar-benar dihitung begitu."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals import agent_eval as ev  # noqa: E402
from evals.arms import ArmResult  # noqa: E402
from tests.agent.conftest import hasil  # noqa: E402


def baris(symbol: str, per_lengan: dict[str, ArmResult]) -> ev.Baris:
    b = ev.Baris(symbol=symbol)
    b.per_lengan = per_lengan
    return b


def arm(nama: str, symbol: str, probes: list[str], skor: float = 70.0,
        escalated: list[str] | None = None) -> ArmResult:
    r = ArmResult(arm=nama, symbol=symbol, probes_run=list(probes),
                  escalated=escalated or [])
    r.results = {p: hasil(p, skor) for p in probes}
    return r


def test_hemat_dihitung_terhadap_baseline_menyeluruh():
    b = baris("FIXA", {
        "menyeluruh": arm("menyeluruh", "FIXA", ["volume_anomaly", "free_float"]),
        "agen": arm("agen", "FIXA", ["volume_anomaly"]),
        "urutan_tetap": arm("urutan_tetap", "FIXA", ["volume_anomaly"]),
        "acak": arm("acak", "FIXA", ["free_float"]),
        "agen_tanpa_harga": arm("agen_tanpa_harga", "FIXA", ["volume_anomaly"]),
    })
    r = ev.ringkas([b], date(2026, 9, 11))
    assert r["lengan"]["agen"]["hemat_persen"] > 0
    assert r["lengan"]["menyeluruh"]["sepakat_persen"] == 100.0


def test_kepekaan_harga_menghitung_pilihan_yang_berbeda():
    sama = baris("FIXA", {
        "menyeluruh": arm("menyeluruh", "FIXA", ["volume_anomaly"]),
        "agen": arm("agen", "FIXA", ["volume_anomaly"]),
        "urutan_tetap": arm("urutan_tetap", "FIXA", ["volume_anomaly"]),
        "acak": arm("acak", "FIXA", ["volume_anomaly"]),
        "agen_tanpa_harga": arm("agen_tanpa_harga", "FIXA", ["volume_anomaly"]),
    })
    beda = baris("FIXB", {
        "menyeluruh": arm("menyeluruh", "FIXB", ["volume_anomaly"]),
        "agen": arm("agen", "FIXB", ["volume_anomaly"]),
        "urutan_tetap": arm("urutan_tetap", "FIXB", ["volume_anomaly"]),
        "acak": arm("acak", "FIXB", ["volume_anomaly"]),
        "agen_tanpa_harga": arm("agen_tanpa_harga", "FIXB", ["broker_concentration"]),
    })
    r = ev.ringkas([sama, beda], date(2026, 9, 11))
    assert r["kepekaan_harga"]["kasus_pilihan_berbeda"] == 1
    assert r["kepekaan_harga"]["persen"] == 50.0


def test_eskalasi_yang_tidak_mengubah_band_tidak_dihitung_berguna():
    # Dua probe berskor sama: membuang salah satunya tidak menggeser band.
    a = arm("agen", "FIXA", ["volume_anomaly", "free_float"], skor=70.0,
            escalated=["free_float"])
    berguna, total = ev.presisi_eskalasi([baris("FIXA", {"agen": a})], date(2026, 9, 11))
    assert (berguna, total) == (0, 1)


def test_eskalasi_yang_menggeser_band_dihitung_berguna():
    a = ArmResult(arm="agen", symbol="FIXA",
                  probes_run=["volume_anomaly", "structural"], escalated=["structural"])
    a.results = {"volume_anomaly": hasil("volume_anomaly", 10.0),
                 "structural": hasil("structural", 95.0)}
    berguna, total = ev.presisi_eskalasi([baris("FIXA", {"agen": a})], date(2026, 9, 11))
    assert (berguna, total) == (1, 1)


def test_laporan_menyebut_pencabutan_klaim_saat_kepekaan_harga_nol():
    b = baris("FIXA", {
        "menyeluruh": arm("menyeluruh", "FIXA", ["volume_anomaly"]),
        "agen": arm("agen", "FIXA", ["volume_anomaly"]),
        "urutan_tetap": arm("urutan_tetap", "FIXA", ["volume_anomaly"]),
        "acak": arm("acak", "FIXA", ["volume_anomaly"]),
        "agen_tanpa_harga": arm("agen_tanpa_harga", "FIXA", ["volume_anomaly"]),
    })
    teks = ev.render(ev.ringkas([b], date(2026, 9, 11)), [b])
    assert "harus dicabut" in teks


def test_kasus_yang_dimuat_punya_bentuk_yang_dijanjikan():
    from evals.build_cases import muat
    kasus = muat()
    assert kasus, "cases.yaml kosong"
    for k in kasus:
        assert k["symbol"].isupper() and len(k["symbol"]) == 4
        assert isinstance(k["sesi"], int) and k["sesi"] >= 40
        assert isinstance(k["pernah_suspend"], bool)


def test_paralel_menghasilkan_urutan_dan_hasil_yang_sama_dengan_serial():
    """Paralelisasi tidak boleh mengubah satu pun angka, juga tidak urutannya.

    Laporan yang bisa diputar ulang harus stabil sampai ke urutan barisnya, dan
    `pool.map` menjaga urutan masukan — tes ini yang mengunci janji itu kalau
    suatu saat ada yang menggantinya dengan `as_completed`.
    """
    from datetime import date

    from evals.build_cases import muat

    kasus = muat()[:4]
    serial = ev.jalankan(kasus, as_of=date(2026, 9, 11), offline=True, pekerja=1)
    paralel = ev.jalankan(kasus, as_of=date(2026, 9, 11), offline=True, pekerja=4)

    assert [b.symbol for b in serial] == [b.symbol for b in paralel]
    for a, b in zip(serial, paralel, strict=True):
        for lengan in a.per_lengan:
            assert a.per_lengan[lengan].credits == b.per_lengan[lengan].credits
            assert a.per_lengan[lengan].band == b.per_lengan[lengan].band
