"""Transport MCP ke sectors-mcp.supertype.ai — klien tulis sendiri. [AD-7]

Kenapa tidak memakai klien MCP jadi: karena klien jadi tidak bisa dicegat. Kalau
tool call MCP lewat klien orang lain, kita tidak tahu berapa kredit yang terbakar,
dan alasan "hanya REST yang bisa diukur" jadi benar. Dengan menulis klien sendiri,
tiap tool call melewati CreditAwareClient yang sama persis seperti REST: pagu
diperiksa, ledger dicatat, cache dipakai.

Bentuk kelasnya sengaja identik dengan RestTransport — fetch(endpoint, params) →
payload mentah, lempar TransportAttemptError kalau gagal. Klien di atasnya tidak
perlu tahu ia sedang bicara MCP atau REST.

**Sesi.** MCP Streamable HTTP itu stateful dan async, sedangkan pipeline kita
sinkron. Sesi dijalankan di event loop milik sendiri di thread terpisah, dibuka
sekali, dipakai ulang, ditutup di close(). Membuka sesi baru tiap tool call akan
menambah dua round trip untuk tiap panggilan.

⚠️  Belum diverifikasi terhadap server sungguhan — butuh API key. Nama tool di
    routing.py adalah asumsi; "make mcp-catalog" menarik katalog asli dan
    menuliskannya ke docs/mcp-catalog.md. Batas keputusan lanjut/REST-only:
    11 Sep, lihat TASK.md §Rencana Cadangan.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from concurrent.futures import Future
from typing import Any

from core.sectors.errors import TransportAttemptError, TransportUnavailable
from core.sectors.redact import get_logger, scrub
from core.sectors.routing import Endpoint

log = get_logger(__name__)

DEFAULT_MCP_URL = "https://sectors-mcp.supertype.ai/mcp"
DEFAULT_TIMEOUT = 45.0


def _import_sdk():
    """SDK MCP opsional: ketiadaannya melumpuhkan MCP, bukan seluruh pipeline."""
    try:
        from mcp import ClientSession  # type: ignore
        from mcp.client.streamable_http import streamablehttp_client  # type: ignore
    except ImportError as exc:  # pragma: no cover — hanya di lingkungan tanpa SDK
        raise TransportUnavailable(
            f"SDK mcp tidak terpasang ({exc}). Jalur REST tetap jalan; "
            "pasang dengan pip install -r requirements.txt kalau MCP dibutuhkan."
        ) from exc
    return ClientSession, streamablehttp_client


class _LoopThread:
    """Event loop asyncio yang hidup di thread sendiri.

    Dipakai supaya sesi MCP yang async bisa dipanggil dari kode sinkron tanpa
    membuka-tutup loop tiap panggilan — dan tanpa memaksa seluruh lajur ingest
    jadi async hanya karena satu transport.
    """

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True, name="mcp-loop")
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro, timeout: float) -> Any:
        fut: Future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return fut.result(timeout=timeout)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5)


class McpTransport:
    """Klien MCP Streamable HTTP dengan sesi yang dipakai ulang."""

    name = "mcp"

    def __init__(
        self,
        api_key: str,
        url: str = DEFAULT_MCP_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.url = url
        self.timeout = timeout
        # MCP memakai skema Bearer; REST memakai kunci telanjang. Beda, dan
        # keduanya sudah pernah bikin orang kehilangan sore hari.
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._loop: _LoopThread | None = None
        self._session: Any = None
        self._ctx: Any = None
        self._lock = threading.Lock()

    # ── sesi ────────────────────────────────────────────────────────────────
    async def _open(self) -> Any:
        ClientSession, streamablehttp_client = _import_sdk()
        self._ctx = streamablehttp_client(self.url, headers=self._headers)
        read, write, _ = await self._ctx.__aenter__()
        session_ctx = ClientSession(read, write)
        session = await session_ctx.__aenter__()
        await session.initialize()
        self._session_ctx = session_ctx
        return session

    def _ensure(self) -> Any:
        with self._lock:
            if self._session is None:
                self._loop = self._loop or _LoopThread()
                try:
                    self._session = self._loop.submit(self._open(), self.timeout)
                except TransportUnavailable:
                    raise
                except Exception as exc:
                    raise TransportAttemptError(
                        f"gagal membuka sesi MCP: {scrub(exc)}", retryable=True
                    ) from exc
            return self._session

    # ── tool call ───────────────────────────────────────────────────────────
    def fetch(self, endpoint: Endpoint, params: dict[str, Any]) -> Any:
        if not endpoint.mcp_tool:
            raise TransportAttemptError(
                f"endpoint '{endpoint.name}' tidak punya tool MCP", retryable=False
            )
        session = self._ensure()
        args = {k: v for k, v in params.items() if v is not None}
        try:
            result = self._loop.submit(  # type: ignore[union-attr]
                session.call_tool(endpoint.mcp_tool, args), self.timeout
            )
        except TimeoutError as exc:
            raise TransportAttemptError(f"timeout tool MCP: {exc}", retryable=True) from exc
        except Exception as exc:
            self._invalidate()
            raise TransportAttemptError(
                f"tool MCP '{endpoint.mcp_tool}' gagal: {scrub(exc)}", retryable=True
            ) from exc

        if getattr(result, "isError", False):
            raise TransportAttemptError(
                f"tool MCP '{endpoint.mcp_tool}' mengembalikan galat: "
                f"{_text_of(result)[:200]}",
                retryable=False, charged=True,
            )
        return _payload_of(result, endpoint.mcp_tool)

    def list_tools(self) -> list[dict]:
        """Katalog tool apa adanya dari server. Dipakai catalog.py. Gratis."""
        session = self._ensure()
        try:
            result = self._loop.submit(session.list_tools(), self.timeout)  # type: ignore[union-attr]
        except Exception as exc:
            raise TransportAttemptError(
                f"gagal menarik katalog MCP: {scrub(exc)}", retryable=True
            ) from exc
        return [
            {
                "name": t.name,
                "description": (t.description or "").strip(),
                "args_schema": getattr(t, "inputSchema", None) or {},
            }
            for t in result.tools
        ]

    def _invalidate(self) -> None:
        """Sesi yang sudah rusak jangan dipakai ulang — retry berikutnya membuka baru."""
        with self._lock:
            self._session = None

    def close(self) -> None:
        with self._lock:
            loop, self._session = self._loop, None
            self._loop = None
        if loop is None:
            return
        try:
            loop.submit(self._close_async(), 10)
        except Exception as exc:
            log.debug("penutupan sesi MCP tidak bersih: %s", scrub(exc))
        finally:
            loop.stop()

    async def _close_async(self) -> None:
        for ctx in (getattr(self, "_session_ctx", None), self._ctx):
            if ctx is not None:
                # Penutupan tidak boleh melempar: sesi yang sudah mati tetap
                # harus melepaskan thread loop-nya.
                with contextlib.suppress(Exception):
                    await ctx.__aexit__(None, None, None)
        self._ctx = None
        self._session_ctx = None


def _text_of(result: Any) -> str:
    parts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _payload_of(result: Any, tool: str) -> Any:
    """Hasil tool MCP → payload seperti REST, supaya parse_rows tidak perlu tahu bedanya.

    Urutan: structuredContent (kalau server menyediakannya) lalu blok teks yang
    diuraikan sebagai JSON. Teks yang bukan JSON dianggap galat bentuk, bukan
    dipaksa jadi data.
    """
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    text = _text_of(result)
    if not text:
        raise TransportAttemptError(
            f"tool MCP '{tool}' mengembalikan hasil kosong", retryable=False, charged=True
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise TransportAttemptError(
            f"hasil tool MCP '{tool}' bukan JSON: {text[:200]}",
            retryable=False, charged=True,
        ) from exc
