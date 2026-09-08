"""CreditAwareClient — satu-satunya pintu keluar jaringan. [AD-3][AD-5][AD-7]

Semua akses ke Sectors lewat sini, REST maupun MCP. Aturan tim nomor 5: nol curl
manual, nol Postman. Bukan karena rapi, tapi karena posisi kredit yang tidak
lengkap sama saja dengan tidak punya posisi kredit — dan jatah kita 1.000.

Urutan yang dijalankan tiap panggilan:

    1. endpoint dicari di tabel perutean      → tidak terdaftar? tolak
    2. cache disk dilihat                     → hit? kembalikan, 0 kredit, TIDAK masuk ledger
    3. pagu fase diperiksa                    → tembus? raise BudgetExceeded
    4. transport dipilih tabel (bukan LLM)    → kirim, retry+backoff kalau layak
    5. respons 200                            → catat belanja ke ledger
    6. payload divalidasi model pydantic      → rusak? SchemaError + simpan ke _rejected/
    7. payload disimpan ke cache permanen

Langkah 5 sengaja mendahului 6: API sudah memotong kredit begitu mengembalikan
200, mau kita bisa membacanya atau tidak. Ledger mencatat apa yang terjadi, bukan
apa yang kita harapkan terjadi.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.env import load_env
from core.sectors import routing
from core.sectors.errors import (
    SchemaError,
    SectorsError,
    TransportAttemptError,
    TransportError,
    TransportUnavailable,
)
from core.sectors.ledger import CreditLedger
from core.sectors.redact import get_logger, install, scrub
from core.sectors.routing import Endpoint, Transport
from core.sectors.schemas import Row, parse_rows

log = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "data" / "cache"

MAX_ATTEMPTS = 4
BACKOFF_BASE = 0.5  # detik; 0,5 → 1 → 2 dengan jitter

# 429 bukan kegagalan biasa: server minta kita PELAN, dan mengulang cepat justru
# memperpanjang hukumannya. Backfill filings kena RATE_LIMIT_EXCEEDED setelah
# belasan halaman beruntun dengan backoff 0,5 detik.
BACKOFF_RATE_LIMIT = 8.0
JEDA_ANTAR_HALAMAN = 0.35

# Kunci ditolak: jangan buang waktu mencoba transport kedua dengan kunci yang sama.
AUTH_STATUS = {401, 403}


@dataclass
class ApiResponse:
    """Hasil satu panggilan, lengkap dengan asal-usul dan biayanya.

    Probe memakai objek ini untuk mengisi EvidenceEntry: source_endpoint,
    source_params, source_transport, dan credits_spent datang dari sini, bukan
    ditulis ulang dengan tangan. Itu yang membuat buku bukti tidak bisa berbohong
    soal dari mana angkanya berasal. [AD-4]
    """

    endpoint: str
    params: dict[str, Any]
    payload: Any
    transport: Transport
    credits_spent: int
    cached: bool
    fetched_at: datetime

    def rows(self, model: type[Row] | None = None) -> list[Row]:
        return parse_rows(self.endpoint, self.payload, model)


@dataclass
class ClientStats:
    """Statistik sesi. Cache hit dilacak di sini, bukan di ledger — ledger hanya
    memuat belanja nyata."""

    calls: int = 0
    cache_hits: int = 0
    credits: int = 0
    retries: int = 0
    by_transport: dict[str, int] = field(default_factory=dict)

    @property
    def hit_rate(self) -> float:
        return self.cache_hits / self.calls if self.calls else 0.0

    def summary(self) -> str:
        return (
            f"{self.calls} panggilan, {self.cache_hits} dari cache "
            f"({self.hit_rate * 100:.0f}%), {self.credits} kredit terpakai"
        )


def canonical_params(params: dict[str, Any]) -> str:
    """Bentuk baku params untuk kunci cache.

    Urut kunci, tanpa spasi, None dibuang. Dua panggilan dengan params sama
    tapi urutan berbeda WAJIB kena cache yang sama — kalau tidak, kita membayar
    dua kali untuk data yang identik.
    """
    clean = {k: v for k, v in sorted(params.items()) if v is not None}
    return json.dumps(clean, sort_keys=True, separators=(",", ":"), default=str)


def cache_key(endpoint: str, params: dict[str, Any]) -> str:
    """Hash (endpoint, params) — transport SENGAJA tidak ikut.

    Data yang sama lewat REST atau MCP adalah data yang sama. Memasukkan
    transport ke kunci berarti membayar dua kali saat fallback. [AD-3]
    """
    raw = f"{endpoint}|{canonical_params(params)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CreditAwareClient:
    """Gateway tunggal ke Sectors.

    Dibuat sekali per proses. Aman dipakai tanpa kunci API selama semua yang
    dipanggil sudah ada di cache — itu yang membuat make demo dan tes probe
    jalan tanpa jaringan.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        phase: str = "dev",
        ledger: CreditLedger | None = None,
        cache_dir: Path | None = None,
        rest: Any | None = None,
        mcp: Any | None = None,
        run_id: str | None = None,
        offline: bool = False,
        allow_reserve: bool = False,
        base_url: str | None = None,
        max_attempts: int = MAX_ATTEMPTS,
        sleep: Any = time.sleep,
    ) -> None:
        # .env dimuat di sini, bukan di tiap pemanggil: ini satu-satunya pintu
        # keluar jaringan, jadi ini juga tempat paling pasti kunci dibutuhkan.
        load_env()
        self.api_key = api_key if api_key is not None else os.environ.get("SECTORS_API_KEY")
        install(self.api_key)  # redaksi dipasang SEBELUM apa pun sempat dicatat

        self.phase = phase
        self.ledger = ledger or CreditLedger()
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE
        self.run_id = run_id
        self.offline = offline
        self.allow_reserve = allow_reserve
        self.base_url = base_url or os.environ.get("SECTORS_REST_BASE")
        self.max_attempts = max_attempts
        self.stats = ClientStats()
        self._sleep = sleep

        self._rest = rest
        self._mcp = mcp
        self._rest_ready = rest is not None
        self._mcp_ready = mcp is not None
        # Kalau pemanggil menyuntik transport sendiri, JANGAN membangun yang lain
        # diam-diam. Tanpa aturan ini, tes yang menyuntik transport palsu bisa
        # jatuh ke fallback dan benar-benar menyentuh jaringan — kelas bug yang
        # baru ketahuan saat tagihan datang.
        self._only_injected = rest is not None or mcp is not None

    # ── transport ───────────────────────────────────────────────────────────
    def _transport(self, name: Transport) -> Any:
        if self._only_injected and not (self._rest_ready if name == "rest" else self._mcp_ready):
            raise TransportUnavailable(
                f"transport '{name}' tidak disuntikkan; klien ini hanya memakai "
                f"transport yang diberikan pemanggil"
            )
        if name == "rest":
            if not self._rest_ready:
                from core.sectors.transport_rest import DEFAULT_BASE, RestTransport

                if not self.api_key:
                    raise TransportUnavailable(
                        "SECTORS_API_KEY tidak diset — jalur REST tidak bisa dipakai. "
                        "Salin .env.example ke .env, atau jalankan mode offline."
                    )
                self._rest = RestTransport(self.api_key, self.base_url or DEFAULT_BASE)
                self._rest_ready = True
            return self._rest

        if not self._mcp_ready:
            from core.sectors.transport_mcp import McpTransport

            if not self.api_key:
                raise TransportUnavailable("SECTORS_API_KEY tidak diset — jalur MCP mati.")
            self._mcp = McpTransport(self.api_key)
            self._mcp_ready = True
        return self._mcp

    # ── cache ───────────────────────────────────────────────────────────────
    def _cache_path(self, endpoint: str, params: dict[str, Any]) -> Path:
        return self.cache_dir / endpoint / f"{cache_key(endpoint, params)}.json"

    def _cache_read(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Cache rusak bukan alasan pipeline mati; anggap saja belum ada.
            log.warning("cache rusak, diabaikan: %s", path.name)
            return None

    def _cache_write(self, path: Path, endpoint: str, params: dict, payload: Any,
                     transport: Transport) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "meta": {
                "endpoint": endpoint,
                "params": params,
                "transport": transport,
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            },
            "payload": payload,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(path)  # atomik: cron yang mati di tengah tidak meninggalkan cache separuh

    # ── panggilan ───────────────────────────────────────────────────────────
    def call(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        phase: str | None = None,
        symbol: str | None = None,
        model: type[Row] | None = None,
        prefer: Transport | None = None,
        validate: bool = True,
    ) -> ApiResponse:
        """Satu panggilan Sectors, termeter dan ter-cache.

        Argumen prefer hanya untuk kode kita sendiri (fallback antar transport).
        Keluaran LLM tidak pernah sampai ke sini.
        """
        params = dict(params or {})
        ep = routing.route(endpoint)  # UnknownEndpoint kalau tidak terdaftar
        phase = phase or self.phase
        self.stats.calls += 1

        # 1. cache — gratis, dan sengaja TIDAK menyentuh ledger.
        path = self._cache_path(endpoint, params)
        hit = self._cache_read(path)
        if hit is not None:
            self.stats.cache_hits += 1
            resp = ApiResponse(
                endpoint=endpoint, params=params, payload=hit.get("payload"),
                transport=hit.get("meta", {}).get("transport", "rest"),
                credits_spent=0, cached=True, fetched_at=datetime.now(UTC),
            )
            if validate:
                resp.rows(model)  # cache beracun ketahuan di sini, bukan di dalam probe
            return resp

        if self.offline:
            raise TransportUnavailable(
                f"mode offline: '{endpoint}' {canonical_params(params)} belum ada di cache. "
                "Jalankan make pipeline / make backfill dengan API key lebih dulu."
            )

        # 2. pagu — raise, bukan warning.
        self.ledger.check(phase, ep.credit_cost, allow_reserve=self.allow_reserve)

        # 3. kirim.
        transport_name = routing.transport_for(endpoint, prefer)
        payload, used_transport = self._send(ep, params, transport_name, phase, symbol)

        # 4. validasi. Ledger sudah dicatat di _send — kredit terpotong walau
        #    kita gagal membacanya.
        if validate:
            try:
                parse_rows(endpoint, payload, model)
            except SchemaError:
                self._quarantine(endpoint, params, payload)
                raise

        self._cache_write(path, endpoint, params, payload, used_transport)
        return ApiResponse(
            endpoint=endpoint, params=params, payload=payload, transport=used_transport,
            credits_spent=ep.credit_cost, cached=False, fetched_at=datetime.now(UTC),
        )

    def _send(
        self, ep: Endpoint, params: dict, transport_name: Transport,
        phase: str, symbol: str | None,
    ) -> tuple[Any, Transport]:
        """Kirim dengan retry, lalu catat belanja. Fallback transport kalau ada."""
        tried: list[Transport] = []
        last_error = "?"

        for name in self._transport_order(ep, transport_name):
            tried.append(name)
            try:
                payload = self._attempt(ep, params, name)
            except TransportAttemptError as exc:
                last_error = exc.detail
                if exc.charged:
                    self._record(ep, params, name, phase, symbol)
                log.warning("transport %s gagal untuk %s: %s", name, ep.name, scrub(exc.detail))
                if exc.status in AUTH_STATUS:
                    # Kunci yang ditolak REST akan ditolak MCP juga. Mencoba
                    # transport kedua cuma menambah satu round trip sia-sia dan
                    # mengaburkan sebab aslinya di log.
                    break
                continue
            except TransportUnavailable as exc:
                last_error = str(exc)
                continue
            self._record(ep, params, name, phase, symbol)
            return payload, name

        raise TransportError(ep.name, len(tried), last_error)

    def _transport_order(self, ep: Endpoint, first: Transport) -> list[Transport]:
        """Transport utama, lalu cadangan kalau endpoint memang punya dua jalur.

        Ini pemenuhan QA M5: MCP mati → fallback REST untuk endpoint yang ada di
        kedua transport, bukan seluruh pipeline tumbang.
        """
        order = [first]
        alt = routing.fallback_for(ep.name, first)
        if alt:
            order.append(alt)
        return order

    def _attempt(self, ep: Endpoint, params: dict, name: Transport) -> Any:
        transport = self._transport(name)
        last: TransportAttemptError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return transport.fetch(ep, params)
            except TransportAttemptError as exc:
                last = exc
                if not exc.retryable or attempt == self.max_attempts:
                    raise
                dasar = BACKOFF_RATE_LIMIT if exc.status == 429 else BACKOFF_BASE
                delay = dasar * (2 ** (attempt - 1)) * (1 + random.random() * 0.3)
                self.stats.retries += 1
                log.info("percobaan %d/%d gagal (%s), tunggu %.1fs",
                         attempt, self.max_attempts, scrub(exc.detail), delay)
                self._sleep(delay)
        raise last if last else TransportAttemptError("gagal tanpa sebab", retryable=False)

    def _record(self, ep: Endpoint, params: dict, transport: Transport,
                phase: str, symbol: str | None) -> None:
        self.ledger.record(
            phase=phase, endpoint=ep.name, transport=transport, credits=ep.credit_cost,
            params_hash=cache_key(ep.name, params)[:16], run_id=self.run_id, symbol=symbol,
        )
        self.stats.credits += ep.credit_cost
        self.stats.by_transport[transport] = self.stats.by_transport.get(transport, 0) + 1

    def _quarantine(self, endpoint: str, params: dict, payload: Any) -> None:
        """Payload yang tidak lolos skema disimpan terpisah, bukan ke cache.

        Kalau masuk cache, satu respons rusak akan terus dipakai selamanya dan
        tidak pernah ditarik ulang. Di _rejected/ ia bisa dibedah tanpa membayar
        lagi untuk melihat bentuknya.
        """
        path = self.cache_dir / "_rejected" / endpoint / f"{cache_key(endpoint, params)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"params": params, "payload": payload}, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        log.error("payload '%s' ditolak skema, disimpan ke %s", endpoint, path.name)

    # ── kenyamanan ──────────────────────────────────────────────────────────
    def rows(self, endpoint: str, params: dict[str, Any] | None = None,
             model: type[Row] | None = None, **kw: Any) -> tuple[list[Row], ApiResponse]:
        """Panggil lalu langsung parse. Mengembalikan (baris, respons) supaya
        pemanggil tetap bisa membaca biaya dan asal-usulnya."""
        resp = self.call(endpoint, params, model=model, **kw)
        return resp.rows(model), resp

    def paginate(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        page_size: int = 100,
        max_pages: int = 50,
        max_credits: int | None = None,
        **kw: Any,
    ) -> tuple[list[Row], int]:
        """Tarik SELURUH halaman satu endpoint. Mengembalikan (baris, kredit).

        Spike F0 menemukan fetch-suspensions melaporkan `total_count: 533` tapi
        hanya mengirim 20 baris per panggilan. Pemanggil yang tidak menelusuri
        halaman akan mengira sudah menarik 24 bulan padahal baru satu — dan
        himpunan positif kalibrasi jadi sepotong tanpa ada yang sadar.

        Dua pagar, dan yang kedua ada karena yang pertama pernah gagal menahan:

        * `max_pages` menghentikan paginasi yang rusak (has_next selamanya True).
        * `max_credits` menghentikan paginasi yang BENAR tapi jauh lebih panjang
          dari perkiraan. fetch-filings 24 bulan pernah menembus 50 halaman
          dengan pagar halaman saja — 50 kredit, tanpa peringatan, untuk rencana
          yang menganggarkan 3. Pagar halaman tidak tahu harga; pagar kredit tahu.
        """
        from core.sectors.schemas import pagination_of

        params = dict(params or {})
        semua: list[Row] = []
        credits = 0
        offset = 0

        for halaman in range(max_pages):
            if max_credits is not None and credits >= max_credits:
                log.warning("paginasi '%s' berhenti di pagu %d kredit; %d baris terambil",
                            endpoint, max_credits, len(semua))
                break
            if halaman:
                # Jeda kecil antar halaman. Paginasi adalah satu-satunya tempat
                # kita menembak berpuluh panggilan beruntun, dan di situlah rate
                # limit menghukum. Jauh lebih murah menunggu sepersekian detik
                # daripada kehilangan seluruh tarikan di halaman ke-50.
                self._sleep(JEDA_ANTAR_HALAMAN)
            try:
                resp = self.call(endpoint, {**params, "limit": page_size, "offset": offset}, **kw)
            except SectorsError as exc:
                # Halaman yang gagal TIDAK boleh membuang halaman yang sudah
                # dibayar. Pernah terjadi sungguhan: 50 kredit terbakar untuk
                # fetch-filings, kena 429 di halaman ke-51, dan seluruh hasilnya
                # hilang karena exception melewati pemanggil. Bayar-lalu-buang
                # adalah kegagalan paling mahal yang bisa dilakukan kode ini.
                log.warning("paginasi '%s' berhenti di halaman %d (%s); %d baris "
                            "yang sudah dibayar tetap dikembalikan",
                            endpoint, halaman + 1, exc, len(semua))
                break

            credits += resp.credits_spent
            semua.extend(resp.rows())

            blok = pagination_of(resp.payload)
            if not blok or not blok.get("has_next"):
                break

            # Server berhak MENGABAIKAN limit yang kita minta — Sectors memangkas
            # 100 jadi ~30. Dilaporkan saja, JANGAN dipakai mengubah permintaan
            # berikutnya: cache permanen berkunci (endpoint, params), jadi limit
            # yang berubah di tengah membuat seluruh halaman berikutnya jadi
            # kunci baru dan DIBAYAR ULANG. Pernah terjadi: 17 kredit hangus
            # untuk suspensi yang sudah ada di cache. Yang menuntun kita ke
            # halaman berikutnya adalah next_offset dari server, bukan aritmetika
            # kita sendiri, jadi ukuran halaman memang tidak perlu kita ketahui.
            nyata = blok.get("limit")
            if halaman == 0 and isinstance(nyata, int) and 0 < nyata < page_size:
                log.info("'%s' memangkas limit %d -> %d (total %s); perkiraan "
                         "halaman di rencana harus memakai angka server",
                         endpoint, page_size, nyata, blok.get("total_count", "?"))

            lanjut = blok.get("next_offset")
            if not isinstance(lanjut, int) or lanjut <= offset:
                log.warning("paginasi '%s' tidak maju di offset %d — dihentikan",
                            endpoint, offset)
                break
            offset = lanjut
            if halaman == max_pages - 1:
                log.warning("paginasi '%s' berhenti di pagar %d halaman; %d baris "
                            "terambil, masih ada sisa di server",
                            endpoint, max_pages, len(semua))
        return semua, credits

    def close(self) -> None:
        for transport in (self._rest, self._mcp):
            if transport is not None and hasattr(transport, "close"):
                try:
                    transport.close()
                except Exception as exc:  # penutupan tidak boleh menjatuhkan pipeline
                    log.warning("gagal menutup transport: %s", scrub(exc))

    def __enter__(self) -> CreditAwareClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
