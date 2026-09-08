"""QA gerbang M1 — CreditAwareClient.

Empat baris QA di TASK_MELCO.md M1 diuji di sini, satu tes satu klaim:

    cache hit tidak menambah ledger   → test_cache_hit_tidak_menambah_ledger
    pagu terlampaui → raise           → test_pagu_tertembus_menolak_bukan_memperingatkan
    key tidak pernah muncul di log    → test_kunci_api_tidak_pernah_muncul_di_log
    respons rusak → error jelas       → test_respons_rusak_memberi_pesan_jelas

Nol jaringan: transport diganti palsu.
"""

from __future__ import annotations

import json
import logging

import pytest

from core.sectors.client import CreditAwareClient, cache_key
from core.sectors.errors import (
    BudgetExceeded,
    SchemaError,
    TransportAttemptError,
    TransportError,
    TransportUnavailable,
    UnknownEndpoint,
)
from core.sectors.ledger import CreditLedger

CLOSE_PAYLOAD = {"data": [{"symbol": "FIXA", "date": "2026-09-05", "close": 1250.0}]}


class FakeTransport:
    """Transport palsu: mencatat panggilan, memutar skenario yang disiapkan."""

    def __init__(self, name="rest", payload=None, raises=None):
        self.name = name
        self.payload = payload if payload is not None else CLOSE_PAYLOAD
        self.raises = list(raises or [])
        self.calls: list[tuple[str, dict]] = []

    def fetch(self, endpoint, params):
        self.calls.append((endpoint.name, dict(params)))
        if self.raises:
            exc = self.raises.pop(0)
            if exc is not None:
                raise exc
        return self.payload

    def close(self):
        pass


@pytest.fixture
def ledger(tmp_path):
    return CreditLedger(tmp_path / "ledger.jsonl", caps={"dev": 10, "daily": 5, "reserve": 100})


@pytest.fixture
def client(tmp_path, ledger):
    return CreditAwareClient(
        api_key="kunci-rahasia-jangan-bocor-123456",
        ledger=ledger,
        cache_dir=tmp_path / "cache",
        rest=FakeTransport(),
        sleep=lambda _: None,
    )


# ── QA 1: cache ─────────────────────────────────────────────────────────────
def test_cache_hit_tidak_menambah_ledger(client, ledger):
    first = client.call("fetch-close", {"date": "2026-09-05"})
    second = client.call("fetch-close", {"date": "2026-09-05"})

    assert first.cached is False and first.credits_spent == 1
    assert second.cached is True and second.credits_spent == 0
    assert ledger.spent("dev") == 1, "panggilan kedua dilayani cache, tidak boleh menambah ledger"
    assert len(ledger.entries()) == 1
    assert client.stats.cache_hits == 1


def test_cache_kebal_urutan_params(client):
    """Params sama dengan urutan berbeda wajib kena cache yang sama —
    kalau tidak, kita membayar dua kali untuk data identik."""
    a = cache_key("fetch-daily-transaction", {"symbol": "FIXA", "start": "2026-01-01"})
    b = cache_key("fetch-daily-transaction", {"start": "2026-01-01", "symbol": "FIXA"})
    assert a == b

    client.call("fetch-daily-transaction", {"symbol": "FIXA", "start": "2026-01-01"},
                model=None, validate=False)
    resp = client.call("fetch-daily-transaction", {"start": "2026-01-01", "symbol": "FIXA"},
                       validate=False)
    assert resp.cached is True


def test_cache_tetap_hidup_antar_instance(tmp_path, ledger):
    """Cache permanen di disk, bukan di memori: proses baru tetap gratis. [AD-3]"""
    kw = dict(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "cache",
              sleep=lambda _: None)
    with CreditAwareClient(rest=FakeTransport(), **kw) as first:
        first.call("fetch-close", {"date": "2026-09-05"})

    transport = FakeTransport()
    with CreditAwareClient(rest=transport, **kw) as second:
        resp = second.call("fetch-close", {"date": "2026-09-05"})

    assert resp.cached is True
    assert transport.calls == [], "instance baru tidak boleh menyentuh jaringan"
    assert ledger.spent("dev") == 1


# ── QA 2: pagu ──────────────────────────────────────────────────────────────
def test_pagu_tertembus_menolak_bukan_memperingatkan(tmp_path):
    ledger = CreditLedger(tmp_path / "l.jsonl", caps={"dev": 2})
    client = CreditAwareClient(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=FakeTransport(), sleep=lambda _: None)
    client.call("fetch-close", {"date": "2026-09-01"})
    client.call("fetch-close", {"date": "2026-09-02"})

    with pytest.raises(BudgetExceeded) as err:
        client.call("fetch-close", {"date": "2026-09-03"})

    assert "pagu fase 'dev' tertembus" in str(err.value)
    assert ledger.spent("dev") == 2, "panggilan yang ditolak tidak boleh ikut tercatat"


def test_cache_hit_tetap_dilayani_walau_pagu_habis(tmp_path):
    """Pagu habis tidak boleh mematikan demo: yang gratis tetap jalan."""
    ledger = CreditLedger(tmp_path / "l.jsonl", caps={"dev": 1})
    client = CreditAwareClient(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=FakeTransport(), sleep=lambda _: None)
    client.call("fetch-close", {"date": "2026-09-01"})
    assert client.call("fetch-close", {"date": "2026-09-01"}).cached is True


def test_cadangan_tidak_bisa_dipakai_tanpa_izin_eksplisit(tmp_path):
    ledger = CreditLedger(tmp_path / "l.jsonl")
    client = CreditAwareClient(api_key="k" * 20, phase="reserve", ledger=ledger,
                               cache_dir=tmp_path / "c", rest=FakeTransport(),
                               sleep=lambda _: None)
    with pytest.raises(BudgetExceeded):
        client.call("fetch-close", {"date": "2026-09-01"})

    longgar = CreditAwareClient(api_key="k" * 20, phase="reserve", ledger=ledger,
                                cache_dir=tmp_path / "c2", rest=FakeTransport(),
                                allow_reserve=True, sleep=lambda _: None)
    assert longgar.call("fetch-close", {"date": "2026-09-01"}).credits_spent == 1


# ── QA 3: redaksi ───────────────────────────────────────────────────────────
def test_kunci_api_tidak_pernah_muncul_di_log(tmp_path, caplog):
    kunci = "sk-sectors-RAHASIA-abcdef123456"
    ledger = CreditTestLedger = CreditLedger(tmp_path / "l.jsonl")
    transport = FakeTransport(raises=[
        TransportAttemptError(f"HTTP 401 Authorization: {kunci}", retryable=True),
        None,
    ])
    client = CreditAwareClient(api_key=kunci, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=transport, sleep=lambda _: None)
    with caplog.at_level(logging.INFO):
        client.call("fetch-close", {"date": "2026-09-05"})

    tercetak = "\n".join(r.getMessage() for r in caplog.records)
    assert kunci not in tercetak, "kunci API bocor ke log"
    assert "REDACTED" in tercetak
    assert CreditTestLedger.spent("dev") == 1


def test_kunci_tidak_bocor_lewat_ledger(tmp_path):
    kunci = "sk-sectors-RAHASIA-abcdef123456"
    ledger = CreditLedger(tmp_path / "l.jsonl")
    client = CreditAwareClient(api_key=kunci, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=FakeTransport(), sleep=lambda _: None)
    client.call("fetch-close", {"date": "2026-09-05"})
    assert kunci not in ledger.path.read_text(encoding="utf-8")


# ── QA 4: respons rusak ─────────────────────────────────────────────────────
def test_respons_rusak_memberi_pesan_jelas(tmp_path, ledger):
    """Bukan KeyError tiga lapis di atas, tapi SchemaError yang menyebut endpoint."""
    transport = FakeTransport(payload={"data": [{"ticker": "FIXA", "close": 1}]})  # tanpa tanggal
    client = CreditAwareClient(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=transport, sleep=lambda _: None)
    with pytest.raises(SchemaError) as err:
        client.call("fetch-close", {"date": "2026-09-05"})

    pesan = str(err.value)
    assert "fetch-close" in pesan and "trade_date" in pesan
    assert ledger.spent("dev") == 1, "kredit sudah terpotong API walau kita gagal membacanya"


def test_payload_rusak_tidak_masuk_cache(tmp_path, ledger):
    transport = FakeTransport(payload={"data": [{"ticker": "FIXA"}]})
    client = CreditAwareClient(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=transport, sleep=lambda _: None)
    with pytest.raises(SchemaError):
        client.call("fetch-close", {"date": "2026-09-05"})

    assert not list((tmp_path / "c" / "fetch-close").glob("*.json"))
    ditolak = list((tmp_path / "c" / "_rejected" / "fetch-close").glob("*.json"))
    assert len(ditolak) == 1, "payload rusak disimpan terpisah untuk dibedah"
    assert json.loads(ditolak[0].read_text())["payload"] == transport.payload


def test_galat_api_disampaikan_apa_adanya(tmp_path, ledger):
    transport = FakeTransport(payload={"error": "rate limit exceeded"})
    client = CreditAwareClient(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=transport, sleep=lambda _: None)
    with pytest.raises(SchemaError, match="rate limit exceeded"):
        client.call("fetch-close", {"date": "2026-09-05"})


# ── perutean, retry, fallback ───────────────────────────────────────────────
def test_endpoint_tak_terdaftar_ditolak(client):
    """Endpoint bebas = biaya tidak diketahui = penganggaran jadi tebakan."""
    with pytest.raises(UnknownEndpoint):
        client.call("fetch-apa-saja", {})


def test_retry_lalu_berhasil(tmp_path, ledger):
    transport = FakeTransport(raises=[
        TransportAttemptError("HTTP 503", retryable=True, status=503),
        TransportAttemptError("HTTP 503", retryable=True, status=503),
        None,
    ])
    client = CreditAwareClient(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=transport, sleep=lambda _: None)
    resp = client.call("fetch-close", {"date": "2026-09-05"})

    assert resp.credits_spent == 1
    assert client.stats.retries == 2
    assert ledger.spent("dev") == 1, "tiga percobaan, satu respons — satu kredit"


def test_galat_tidak_layak_retry_langsung_menyerah(tmp_path, ledger):
    transport = FakeTransport(raises=[
        TransportAttemptError("HTTP 401", retryable=False, status=401)
    ] * 4)
    client = CreditAwareClient(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=transport, sleep=lambda _: None)
    with pytest.raises(TransportError):
        client.call("fetch-close", {"date": "2026-09-05"})

    assert client.stats.retries == 0
    assert ledger.spent("dev") == 0, "401 tidak memotong kredit"


def test_mcp_mati_jatuh_ke_rest(tmp_path, ledger):
    """QA M5: satu transport tumbang tidak menjatuhkan seluruh pipeline."""
    mcp = FakeTransport("mcp", raises=[TransportAttemptError("MCP mati", retryable=False)] * 4)
    rest = FakeTransport("rest", payload={"data": [{"symbol": "FIXA", "free_float": 4.0}]})
    client = CreditAwareClient(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "c",
                               rest=rest, mcp=mcp, sleep=lambda _: None)

    # fetch-free-float lebih suka MCP; ia juga tidak punya jalur REST, jadi
    # dipakai endpoint dua-jalur untuk membuktikan fallback benar-benar terjadi.
    resp = client.call("fetch-daily-transaction", {"symbol": "FIXA", "start": "2026-09-01"},
                       prefer="mcp", validate=False)
    assert resp.transport == "rest"
    assert len(mcp.calls) == 1 and len(rest.calls) == 1


def test_endpoint_satu_jalur_tidak_punya_cadangan(tmp_path, ledger):
    mcp = FakeTransport("mcp", raises=[TransportAttemptError("MCP mati", retryable=False)])
    client = CreditAwareClient(api_key="k" * 20, ledger=ledger, cache_dir=tmp_path / "c",
                               mcp=mcp, sleep=lambda _: None)
    with pytest.raises(TransportError):
        client.call("fetch-free-float", {"symbol": "FIXA"})


# ── mode offline ────────────────────────────────────────────────────────────
def test_offline_menolak_menyentuh_jaringan(tmp_path, ledger):
    """Inilah yang membuat make demo dan tes probe terbukti tanpa jaringan. [AD-2]"""
    client = CreditAwareClient(ledger=ledger, cache_dir=tmp_path / "c", offline=True)
    with pytest.raises(TransportUnavailable, match="mode offline"):
        client.call("fetch-close", {"date": "2026-09-05"})
    assert ledger.spent("dev") == 0


def test_offline_tetap_melayani_cache(tmp_path, ledger):
    kw = dict(ledger=ledger, cache_dir=tmp_path / "c")
    CreditAwareClient(api_key="k" * 20, rest=FakeTransport(), sleep=lambda _: None,
                      **kw).call("fetch-close", {"date": "2026-09-05"})

    offline = CreditAwareClient(offline=True, **kw)
    resp = offline.call("fetch-close", {"date": "2026-09-05"})
    assert resp.cached is True and resp.credits_spent == 0


def test_tanpa_kunci_pesannya_menuntun(tmp_path, ledger):
    client = CreditAwareClient(api_key="", ledger=ledger, cache_dir=tmp_path / "c")
    with pytest.raises(TransportError, match="SECTORS_API_KEY"):
        client.call("fetch-close", {"date": "2026-09-05"})
