"""Perkakas bersama tes probe. Nol jaringan, nol API key."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from core.ingest.warehouse import Warehouse
from core.probes.base import Context

MINI = Path(__file__).resolve().parents[2] / "fixtures" / "warehouse-mini"
AS_OF = date(2026, 9, 5)  # Sabtu — hari bursa terakhir yang terlihat 2026-09-04


@pytest.fixture(scope="session")
def mini() -> Warehouse:
    if not (MINI / "daily_close.parquet").exists():
        pytest.fail("fixtures/warehouse-mini/ belum dibangkitkan — jalankan make warehouse-mini")
    return Warehouse(MINI)


@pytest.fixture
def ctx(mini: Warehouse) -> Context:
    """Konteks tanpa klien: probe WAJIB bisa jalan sepenuhnya dari warehouse."""
    return Context(as_of=AS_OF, warehouse=mini, client=None, budget_remaining=25)
