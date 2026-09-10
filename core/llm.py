"""Satu pintu ke LLM. Dipakai perencana, penyelidik, dan narasi.

Dua penyedia, satu SDK. MiniMax M3 Anthropic-compatible — request, tool use,
dan bentuk respons identik; yang berbeda hanya base_url, kunci, dan nama model.
https://platform.minimax.io/docs/api-reference/text-anthropic-api

Ditulis sebagai seam bersama supaya tiga lajur tidak melahirkan tiga klien yang
berbeda perilakunya. Empat hal ditegakkan di sini, bukan di enam pemanggil:

1. **Keluaran terstruktur.** Perencana dan penyelidik tidak pernah mengembalikan
   prosa. `ask_json()` memvalidasi ke model pydantic; yang tidak lolos diulang
   sekali dengan pesan galat, lalu menyerah dengan JSONInvalid. Menyerah adalah
   perilaku yang benar — pemanggil punya fallback deterministik. [AD-4]
2. **Cache di disk.** Berkunci (penyedia, model, versi prompt, isi permintaan).
   Eval agen menjalankan puluhan kasus berulang kali; tanpa cache, ongkosnya
   naik linear terhadap jumlah percobaan tanpa menambah informasi. [K9]
3. **Anggaran token terpisah dari kredit Sectors.** Dicatat ke
   data/llm_ledger.jsonl supaya pemakaian LLM bisa dipertanggungjawabkan
   terpisah — dua sumber biaya yang berbeda tidak boleh tercampur. [K9]
4. **Bisa dipalsukan.** FakeLLM membuat seluruh lajur agen tertes tanpa jaringan
   dan tanpa kunci — syarat `make demo` jalan di mesin juri. [AD-1]

    from core.llm import LLM
    llm = LLM.from_env()
    plan = llm.ask_json(Plan, system=..., prompt=..., prompt_version="planner-v1")
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.env import load_env  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "llm_cache"
LEDGER = ROOT / "data" / "llm_ledger.jsonl"

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Kegagalan yang tidak bisa dipulihkan sendiri oleh klien."""


class JSONInvalid(LLMError):
    """Model gagal menghasilkan JSON yang lolos skema, bahkan setelah diulang.

    Pemanggil WAJIB menangani ini dengan fallback deterministik, bukan
    meneruskannya ke atas. Agen yang mati karena LLM ngelantur melanggar AD-6.
    """


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str | None
    key_env: str
    model: str
    model_eval: str
    supports_temperature: bool = False
    """SDK Anthropic 1.x menghapus `temperature` dari Messages.create() dan
    menggantinya dengan `output_config.effort`. MiniMax masih mendokumentasikan
    `temperature` (rentang [0,2]) di endpoint Anthropic-compatible-nya, jadi
    untuk penyedia itu kita kirim lewat extra_body. Menyetel bendera ini
    per-penyedia, bukan membuang temperature diam-diam, supaya determinisme
    yang kita klaim di eval agen benar-benar diminta ke server yang menerimanya.
    https://platform.minimax.io/docs/api-reference/text-anthropic-api"""


def _providers() -> dict[str, Provider]:
    return {
        "claude": Provider(
            name="claude",
            base_url=None,  # bawaan SDK
            key_env="ANTHROPIC_API_KEY",
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-5"),
            model_eval=os.getenv("CLAUDE_MODEL_EVAL", "claude-haiku-4-5-20251001"),
            supports_temperature=False,
        ),
        "minimax": Provider(
            name="minimax",
            base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/anthropic"),
            key_env="MINIMAX_API_KEY",
            model=os.getenv("MINIMAX_MODEL", "MiniMax-M3"),
            model_eval=os.getenv("MINIMAX_MODEL_EVAL", "MiniMax-M2.7-highspeed"),
            supports_temperature=True,
        ),
    }


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    cache_hits: int = 0


class LLM:
    """Klien LLM dengan keluaran terstruktur, cache, dan ledger."""

    def __init__(self, provider: Provider, *, eval_mode: bool = False,
                 cache_dir: Path | None = None, client: Any = None) -> None:
        self.provider = provider
        self.model = provider.model_eval if eval_mode else provider.model
        self.cache_dir = cache_dir or CACHE_DIR
        self.usage = Usage()
        self._client = client

    # ── konstruksi ──────────────────────────────────────────────────────────
    @classmethod
    def from_env(cls, *, eval_mode: bool = False, provider: str | None = None) -> LLM:
        load_env()
        name = (provider or os.getenv("PANTAU_LLM_PROVIDER", "claude")).strip().lower()
        providers = _providers()
        if name not in providers:
            raise LLMError(
                f"PANTAU_LLM_PROVIDER '{name}' tidak dikenal. Pilih: {', '.join(providers)}"
            )
        p = providers[name]
        if not os.getenv(p.key_env):
            raise LLMError(
                f"{p.key_env} belum diisi di .env — dibutuhkan penyedia '{name}'. "
                f"Ganti PANTAU_LLM_PROVIDER kalau mau memakai penyedia lain."
            )
        return cls(p, eval_mode=eval_mode)

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise LLMError("paket 'anthropic' belum terpasang — jalankan make setup") from exc
            kwargs: dict[str, Any] = {"api_key": os.environ[self.provider.key_env]}
            if self.provider.base_url:
                kwargs["base_url"] = self.provider.base_url
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    # ── permintaan ──────────────────────────────────────────────────────────
    def ask_json(self, schema: type[T], *, system: str, prompt: str,
                 prompt_version: str, max_tokens: int = 2000,
                 temperature: float = 0.0, retries: int = 1) -> T:
        """Minta JSON yang lolos `schema`. Melempar JSONInvalid kalau gagal.

        Dijalankan lewat tool use, bukan "tolong balas JSON": penyedia menjamin
        bentuknya, jadi kita tidak perlu mengurai prosa yang dibungkus pagar
        markdown. MiniMax mendukung tool use penuh sama seperti Claude.
        """
        tool = {
            "name": "jawab",
            "description": f"Kembalikan jawaban sesuai skema {schema.__name__}.",
            "input_schema": schema.model_json_schema(),
        }
        messages = [{"role": "user", "content": prompt}]
        last_error = ""

        for attempt in range(retries + 1):
            raw = self._call(system=system, messages=messages, tools=[tool],
                             tool_choice={"type": "tool", "name": "jawab"},
                             max_tokens=max_tokens, temperature=temperature,
                             prompt_version=prompt_version)
            try:
                return schema.model_validate(raw)
            except ValidationError as exc:
                last_error = str(exc)[:600]
                log.warning("keluaran %s tidak lolos skema (percobaan %d): %s",
                            prompt_version, attempt + 1, last_error.splitlines()[0])
                if attempt < retries:
                    # Satu giliran user, bukan riwayat percakapan palsu. Giliran
                    # asisten yang benar berisi blok tool_use, bukan teks JSON —
                    # dan MiniMax mewajibkan respons model dilampirkan utuh untuk
                    # menjaga kontinuitas. Memalsukannya membuat percobaan kedua
                    # mengembalikan respons tanpa blok tool_use sama sekali,
                    # sehingga retry justru lebih sering gagal daripada berhasil.
                    # Ditemukan saat uji end-to-end MiniMax pertama.
                    messages = [{"role": "user", "content": (
                        f"{prompt}\n\n---\nPercobaan sebelumnya menghasilkan:\n"
                        f"{json.dumps(raw, ensure_ascii=False)[:1500]}\n\n"
                        f"Itu tidak lolos skema:\n{last_error}\n\n"
                        f"Perbaiki dan panggil tool 'jawab' sekali lagi."
                    )}]

        raise JSONInvalid(
            f"{prompt_version}: keluaran tidak lolos skema setelah {retries + 1} percobaan. "
            f"{last_error}"
        )

    def ask_text(self, *, system: str, prompt: str, prompt_version: str,
                 max_tokens: int = 800, temperature: float = 0.0) -> str:
        """Prosa bebas. Satu-satunya pemakaian sah: narasi, yang lewat validator
        sitasi sesudahnya. Jangan pernah dipakai untuk keputusan agen. [AD-4]"""
        out = self._call(system=system, messages=[{"role": "user", "content": prompt}],
                         tools=None, tool_choice=None, max_tokens=max_tokens,
                         temperature=temperature, prompt_version=prompt_version)
        return out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)

    # ── jalur bersama ───────────────────────────────────────────────────────
    def _call(self, *, system: str, messages: list[dict], tools: list | None,
              tool_choice: dict | None, max_tokens: int, temperature: float,
              prompt_version: str) -> Any:
        key = self._cache_key(system, messages, tools, prompt_version, max_tokens, temperature)
        cached = self._cache_read(key)
        if cached is not None:
            self.usage.cache_hits += 1
            return cached

        kwargs: dict[str, Any] = {
            "model": self.model, "max_tokens": max_tokens,
            "system": system, "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        if self.provider.supports_temperature:
            # Lewat extra_body: SDK 1.x tidak lagi punya parameter bernama ini,
            # tapi server MiniMax masih membacanya dari badan permintaan.
            kwargs["extra_body"] = {"temperature": temperature}

        started = time.monotonic()
        try:
            resp = self.client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 — dibungkus supaya pemanggil
            # cuma perlu menangani LLMError, bukan galat SDK tiap penyedia.
            raise LLMError(f"{self.provider.name}/{self.model}: {type(exc).__name__}: {exc}") from exc

        result = self._extract(resp, expect_tool=bool(tools))
        self._record(resp, prompt_version, time.monotonic() - started)
        self._cache_write(key, result)
        return result

    @staticmethod
    def _extract(resp: Any, *, expect_tool: bool) -> Any:
        for block in getattr(resp, "content", []) or []:
            if expect_tool and getattr(block, "type", None) == "tool_use":
                return block.input
            if not expect_tool and getattr(block, "type", None) == "text":
                return block.text
        raise LLMError(
            "respons tidak memuat blok yang diharapkan "
            f"({'tool_use' if expect_tool else 'text'}) — model menolak atau terpotong"
        )

    def _record(self, resp: Any, prompt_version: str, seconds: float) -> None:
        u = getattr(resp, "usage", None)
        inp = int(getattr(u, "input_tokens", 0) or 0)
        out = int(getattr(u, "output_tokens", 0) or 0)
        self.usage.input_tokens += inp
        self.usage.output_tokens += out
        self.usage.calls += 1
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "provider": self.provider.name, "model": self.model,
                "prompt_version": prompt_version,
                "input_tokens": inp, "output_tokens": out,
                "seconds": round(seconds, 2),
            }, ensure_ascii=False) + "\n")

    # ── cache ───────────────────────────────────────────────────────────────
    def _cache_key(self, system: str, messages: list[dict], tools: list | None,
                   prompt_version: str, max_tokens: int, temperature: float) -> str:
        payload = json.dumps({
            "provider": self.provider.name, "model": self.model,
            "prompt_version": prompt_version, "system": system,
            "messages": messages, "tools": tools,
            "max_tokens": max_tokens, "temperature": temperature,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def _cache_read(self, key: str) -> Any | None:
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))["result"]
        except (OSError, ValueError, KeyError):
            return None

    def _cache_write(self, key: str, result: Any) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / f"{key}.json").write_text(
            json.dumps({"result": result}, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ── palsu untuk tes ─────────────────────────────────────────────────────────
@dataclass
class FakeLLM:
    """LLM deterministik untuk tes dan `make demo`. Tanpa jaringan, tanpa kunci.

    `responses` dipetakan dari prompt_version → jawaban (atau daftar jawaban
    berurutan, untuk loop penyelidik yang memanggil berkali-kali).
    """

    responses: dict[str, Any] = field(default_factory=dict)
    calls: list[tuple[str, str]] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    model: str = "fake"
    fail_schema_for: set[str] = field(default_factory=set)
    """prompt_version di sini akan selalu melempar JSONInvalid — untuk menguji
    jalur fallback deterministik."""

    def ask_json(self, schema: type[T], *, system: str, prompt: str,
                 prompt_version: str, **_: Any) -> T:
        self.calls.append((prompt_version, prompt))
        if prompt_version in self.fail_schema_for:
            raise JSONInvalid(f"{prompt_version}: dipalsukan gagal skema")
        return schema.model_validate(self._next(prompt_version))

    def ask_text(self, *, system: str, prompt: str, prompt_version: str, **_: Any) -> str:
        self.calls.append((prompt_version, prompt))
        if prompt_version in self.fail_schema_for:
            raise JSONInvalid(f"{prompt_version}: dipalsukan gagal")
        return str(self._next(prompt_version))

    def _next(self, prompt_version: str) -> Any:
        if prompt_version not in self.responses:
            raise JSONInvalid(f"FakeLLM tidak punya jawaban untuk '{prompt_version}'")
        value = self.responses[prompt_version]
        if isinstance(value, list):
            if not value:
                raise JSONInvalid(f"FakeLLM kehabisan jawaban untuk '{prompt_version}'")
            return value.pop(0)
        return value
