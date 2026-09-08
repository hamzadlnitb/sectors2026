"""Transport MCP — kontrak dengan SDK, diuji tanpa menyentuh server. [AD-7]

Spike F0 menggagalkan lima endpoint bukan karena API Sectors, melainkan karena
satu nama fungsi salah tebak: `streamablehttp_client` vs `streamable_http_client`.
Kegagalannya baru terlihat setelah kredit dibelanjakan.

Tes di sini mengunci permukaan SDK yang benar-benar dipakai. Nol jaringan: yang
diperiksa apakah kodenya bisa MENYUSUN sesi, bukan apakah servernya menjawab.
"""

from __future__ import annotations

import pytest

from core.sectors.errors import TransportAttemptError
from core.sectors.routing import route
from core.sectors.transport_mcp import (
    DEFAULT_MCP_URL,
    McpTransport,
    _http_client,
    _import_sdk,
    _payload_of,
    _text_of,
)


# ── permukaan SDK ───────────────────────────────────────────────────────────
def test_nama_fungsi_sdk_benar():
    """Yang salah tebak di v1 dan bikin lima endpoint gagal."""
    ClientSession, klien = _import_sdk()
    assert klien.__name__ == "streamable_http_client"
    assert hasattr(ClientSession, "initialize")


def test_sdk_meng_yield_dua_aliran_bukan_tiga():
    """Bentuk lama (read, write, get_session_id) sudah tidak berlaku.
    Kalau SDK berubah lagi, tes ini yang merah duluan — bukan spike berbayar."""
    from mcp.client.streamable_http import TransportStreams

    assert len(TransportStreams.__args__) == 2


def test_klien_http_membawa_header_otorisasi():
    """streamable_http_client TIDAK menerima argumen headers — satu-satunya
    jalan menyisipkan kunci adalah lewat klien httpx yang sudah dikonfigurasi."""
    import asyncio

    klien = _http_client({"Authorization": "Bearer rahasia"}, 10.0)
    try:
        assert klien.headers["Authorization"] == "Bearer rahasia"
    finally:
        asyncio.run(klien.aclose())


def test_mcp_memakai_skema_bearer():
    """REST memakai kunci telanjang, MCP memakai Bearer. Beda, dan keduanya
    sudah pernah bikin orang kehilangan sore hari."""
    t = McpTransport("kunci-uji-1234567890")
    assert t._headers["Authorization"].startswith("Bearer ")
    assert t.url == DEFAULT_MCP_URL


# ── perilaku tanpa jaringan ─────────────────────────────────────────────────
def test_endpoint_tanpa_tool_mcp_ditolak_sebelum_menyambung():
    """Menolak lebih awal: membuka sesi untuk endpoint yang memang tidak punya
    tool MCP cuma membuang satu round trip."""
    from dataclasses import replace

    ep = replace(route("fetch-close"), mcp_tool=None)
    t = McpTransport("kunci-uji-1234567890")
    with pytest.raises(TransportAttemptError, match="tidak punya tool MCP") as err:
        t.fetch(ep, {"date": "2026-09-07"})
    assert err.value.retryable is False


def test_tutup_tanpa_pernah_menyambung_aman():
    """cron yang mati sebelum sesi terbuka tidak boleh meninggalkan exception."""
    McpTransport("kunci-uji-1234567890").close()


# ── penerjemahan hasil tool ─────────────────────────────────────────────────
class FakeBlock:
    def __init__(self, text):
        self.text = text


class FakeResult:
    def __init__(self, text=None, structured=None, error=False):
        self.content = [FakeBlock(text)] if text else []
        self.structuredContent = structured
        self.isError = error


def test_structured_content_diutamakan():
    hasil = FakeResult(text='{"a": 2}', structured={"data": [{"symbol": "BBCA"}]})
    assert _payload_of(hasil, "t") == {"data": [{"symbol": "BBCA"}]}


def test_blok_teks_diurai_sebagai_json():
    assert _payload_of(FakeResult(text='{"data": []}'), "t") == {"data": []}


def test_hasil_kosong_ditolak_dan_dianggap_terpotong():
    """Tool call yang menjawab kosong tetap memotong kredit — ledger harus tahu."""
    with pytest.raises(TransportAttemptError) as err:
        _payload_of(FakeResult(), "get_free_float")
    assert err.value.charged is True


def test_teks_bukan_json_tidak_dipaksa_jadi_data():
    with pytest.raises(TransportAttemptError, match="bukan JSON"):
        _payload_of(FakeResult(text="Rate limit exceeded"), "t")


def test_teks_beberapa_blok_digabung():
    hasil = FakeResult()
    hasil.content = [FakeBlock("baris1"), FakeBlock("baris2")]
    assert _text_of(hasil) == "baris1\nbaris2"
