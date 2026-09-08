"""Transport REST ke Sectors API v2.

Sengaja bodoh: bangun URL, kirim, kembalikan JSON mentah. Cache, ledger, pagu,
retry, dan redaksi ada di CreditAwareClient — supaya jalur MCP mendapat perlakuan
yang persis sama tanpa menyalin logika. [AD-7]

Kunci dikirim di header Authorization tanpa skema (bukan Bearer); itu bentuk yang
dipakai Sectors API v2. Jalur MCP memakai Bearer — lihat transport_mcp.py.
"""

from __future__ import annotations

import string
from typing import Any

import httpx

from core.sectors.errors import TransportAttemptError
from core.sectors.redact import get_logger
from core.sectors.routing import Endpoint

log = get_logger(__name__)

DEFAULT_BASE = "https://api.sectors.app/v2"
DEFAULT_TIMEOUT = 30.0

# 429 dan 5xx: server minta ditunggu. 408/425: permintaan tidak pernah diproses.
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def build_path(endpoint: Endpoint, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Isi placeholder jalur dari params; sisanya jadi query string.

    Mengembalikan (jalur, params_sisa) supaya pemanggil tahu persis apa yang
    dikirim — itu yang masuk ke source_params di buku bukti.
    """
    if not endpoint.rest_path:
        raise TransportAttemptError(
            f"endpoint '{endpoint.name}' tidak punya jalur REST", retryable=False
        )
    fields = {f for _, f, _, _ in string.Formatter().parse(endpoint.rest_path) if f}
    missing = fields - params.keys()
    if missing:
        raise TransportAttemptError(
            f"params kurang untuk '{endpoint.name}': {sorted(missing)}", retryable=False
        )
    path = endpoint.rest_path.format(**{k: params[k] for k in fields})
    rest = {k: v for k, v in params.items() if k not in fields and v is not None}
    return path, rest


class RestTransport:
    """Klien HTTP tipis. Satu instance per proses; koneksi dipakai ulang."""

    name = "rest"

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._own_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"Authorization": api_key, "Accept": "application/json"},
            follow_redirects=True,
        )

    def fetch(self, endpoint: Endpoint, params: dict[str, Any]) -> Any:
        path, query = build_path(endpoint, params)
        url = f"{self.base_url}{path}"
        try:
            resp = self._client.get(url, params=query)
        except httpx.TimeoutException as exc:
            raise TransportAttemptError(f"timeout: {exc}", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise TransportAttemptError(f"jaringan: {exc}", retryable=True) from exc

        if resp.status_code in RETRYABLE_STATUS:
            # 429 hampir pasti TIDAK memotong kredit; 5xx belum tentu. Dianggap
            # tidak terpotong supaya ledger tidak mengklaim belanja yang tidak ada —
            # kalau meleset, arahnya konservatif ke sisi kita sendiri.
            raise TransportAttemptError(
                f"HTTP {resp.status_code}", retryable=True, status=resp.status_code
            )
        if resp.status_code >= 400:
            raise TransportAttemptError(
                f"HTTP {resp.status_code}: {resp.text[:200]}",
                retryable=False, status=resp.status_code,
            )
        try:
            return resp.json()
        except ValueError as exc:
            # Sampai 200 tapi bukan JSON: kredit kemungkinan besar sudah terpotong.
            raise TransportAttemptError(
                f"respons 200 bukan JSON: {resp.text[:200]}",
                retryable=False, status=resp.status_code, charged=True,
            ) from exc

    def close(self) -> None:
        if self._own_client:
            self._client.close()
