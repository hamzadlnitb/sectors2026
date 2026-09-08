""".env harus benar-benar terbaca.

.env.example menyuruh orang menyalin berkasnya lalu mengisi kunci. Sebelum tes
ini ada, tidak ada satu pun kode yang memuatnya — perintah pertama yang
dijalankan orang akan gagal dengan "SECTORS_API_KEY tidak diset" padahal
kuncinya sudah ada di berkas, dan yang dicurigai duluan pasti kuncinya.
"""

from __future__ import annotations

import core.env as env
from core.sectors.client import CreditAwareClient


def _reset():
    env._loaded = False


def test_kunci_di_env_terbaca(tmp_path, monkeypatch):
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)
    berkas = tmp_path / ".env"
    berkas.write_text('SECTORS_API_KEY=kunci-dari-berkas-env-123\n', encoding="utf-8")

    _reset()
    assert env.load_env(berkas) is True
    assert env.os.environ["SECTORS_API_KEY"] == "kunci-dari-berkas-env-123"


def test_lingkungan_menang_atas_berkas(tmp_path, monkeypatch):
    """GitHub Actions memberi kunci lewat Secrets, tanpa .env sama sekali.
    .env yang tidak sengaja terbawa ke runner tidak boleh menang atas Secrets."""
    monkeypatch.setenv("SECTORS_API_KEY", "kunci-dari-secrets")
    berkas = tmp_path / ".env"
    berkas.write_text("SECTORS_API_KEY=kunci-dari-berkas\n", encoding="utf-8")

    _reset()
    env.load_env(berkas)
    assert env.os.environ["SECTORS_API_KEY"] == "kunci-dari-secrets"


def test_tanpa_berkas_bukan_kesalahan(tmp_path):
    _reset()
    assert env.load_env(tmp_path / "tidak-ada.env") is False


def test_komentar_dan_baris_kosong_dilewati(tmp_path, monkeypatch):
    monkeypatch.delenv("SECTORS_MCP_URL", raising=False)
    berkas = tmp_path / ".env"
    berkas.write_text(
        "# ini komentar\n\nSECTORS_MCP_URL=https://contoh/mcp\n", encoding="utf-8")

    _reset()
    env._parse_simple(berkas)  # jalur cadangan, tanpa python-dotenv
    assert env.os.environ["SECTORS_MCP_URL"] == "https://contoh/mcp"


def test_tanda_kutip_dilepas(tmp_path, monkeypatch):
    """Orang akan menulis KEY="..." karena terbiasa dari shell."""
    monkeypatch.delenv("SECTORS_REST_BASE", raising=False)
    berkas = tmp_path / ".env"
    berkas.write_text('SECTORS_REST_BASE="https://api.sectors.app/v2"\n', encoding="utf-8")

    _reset()
    env._parse_simple(berkas)
    assert env.os.environ["SECTORS_REST_BASE"] == "https://api.sectors.app/v2"


def test_gateway_memuat_env_sendiri(tmp_path, monkeypatch):
    """Pemanggil tidak perlu tahu soal .env — gateway yang mengurusnya."""
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)
    berkas = tmp_path / ".env"
    berkas.write_text("SECTORS_API_KEY=kunci-lewat-gateway-456\n", encoding="utf-8")
    monkeypatch.setattr(env, "ENV_PATH", berkas)

    _reset()
    client = CreditAwareClient(cache_dir=tmp_path / "c")
    assert client.api_key == "kunci-lewat-gateway-456"


def test_kunci_dari_env_ikut_diredaksi(tmp_path, monkeypatch, caplog):
    """Kunci yang datang dari berkas harus disensor sama seperti yang dari
    lingkungan — kalau tidak, jalur .env jadi celah kebocoran."""
    import logging

    from core.sectors.redact import MASK, get_logger

    rahasia = "sk-dari-env-yang-rahasia-789"
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)
    berkas = tmp_path / ".env"
    berkas.write_text(f"SECTORS_API_KEY={rahasia}\n", encoding="utf-8")
    monkeypatch.setattr(env, "ENV_PATH", berkas)

    _reset()
    CreditAwareClient(cache_dir=tmp_path / "c")

    log = get_logger("tes.env")
    with caplog.at_level(logging.WARNING, logger="tes.env"):
        log.warning("gagal auth dengan %s", rahasia)
    assert rahasia not in caplog.text
    assert MASK in caplog.text
