"""Model pydantic untuk respons Sectors.

Kenapa ada lapisan ini, padahal API-nya sudah mengembalikan JSON: supaya respons
rusak berhenti **di sini**, dengan pesan yang menyebut endpoint dan cuplikan
payload — bukan meledak jadi KeyError di tengah probe, tiga lapis di atas, saat
cron jalan jam setengah enam sore tanpa ada yang menonton.

Dua kompromi yang disengaja:

* **Alias longgar, isi ketat.** Nama kolom Sectors belum diverifikasi spike F0
  (lihat routing.py), jadi tiap field menerima beberapa ejaan yang masuk akal
  (symbol/ticker, date/trade_date). Yang TIDAK longgar: field wajib tetap wajib,
  dan tipenya tetap divalidasi. Begitu spike selesai, alias yang tidak terpakai
  boleh dibuang — tapi tidak ada yang rusak kalau dibiarkan.
* **extra="ignore".** Sectors boleh menambah kolom kapan saja; itu bukan alasan
  pipeline harian mati.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from core.sectors.errors import SchemaError

SYMBOL_RE = re.compile(r"^[A-Z]{4}$")


def normalize_symbol(value: str) -> str:
    """Buang sufiks .JK dan naikkan ke kapital.

    Dokumen Sectors eksplisit menolak sufiks .JK, dan kontrak tim mematok
    ^[A-Z]{4}$. Normalisasi dilakukan sekali di sini supaya tidak ada yang
    mengulang re.sub di enam probe. [contracts/CHANGES.md C1 #5]
    """
    sym = str(value).strip().upper()
    if sym.endswith(".JK"):
        sym = sym[:-3]
    return sym


class Row(BaseModel):
    """Induk semua baris respons. Longgar terhadap kolom tambahan, ketat pada isi."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class SymbolRow(Row):
    symbol: str = Field(validation_alias=AliasChoices("symbol", "ticker", "kode", "stock"))

    @field_validator("symbol", mode="before")
    @classmethod
    def _clean(cls, v: Any) -> Any:
        return normalize_symbol(v) if isinstance(v, str) else v

    @field_validator("symbol")
    @classmethod
    def _shape(cls, v: str) -> str:
        if not SYMBOL_RE.match(v):
            raise ValueError(f"ticker '{v}' bukan bentuk IDX 4 huruf")
        return v


# ── Tier 1 ──────────────────────────────────────────────────────────────────
class ClosePrice(SymbolRow):
    """fetch-close — satu panggilan = seluruh ticker IDX pada satu tanggal."""

    trade_date: date = Field(validation_alias=AliasChoices("trade_date", "date", "tanggal"))
    close_price: float | None = Field(
        default=None, validation_alias=AliasChoices("close_price", "close", "price")
    )


class MostTraded(SymbolRow):
    trade_date: date | None = Field(
        default=None, validation_alias=AliasChoices("trade_date", "date")
    )
    volume: int | None = None
    price: float | None = Field(default=None, validation_alias=AliasChoices("price", "close"))


class TopChange(SymbolRow):
    price_change: float | None = Field(
        default=None, validation_alias=AliasChoices("price_change", "change", "pct_change")
    )
    last_close: float | None = Field(
        default=None, validation_alias=AliasChoices("last_close", "close", "price")
    )


class Suspension(SymbolRow):
    """Sumber label kalibrasi Hamzah. reason yang kosong tetap diterima —
    ketiadaan alasan itu sendiri informasi, dan kalibrasi yang menyaringnya."""

    start_date: date = Field(
        validation_alias=AliasChoices("start_date", "suspension_date", "date", "start")
    )
    end_date: date | None = Field(
        default=None, validation_alias=AliasChoices("end_date", "resume_date", "end")
    )
    reason: str | None = Field(
        default=None, validation_alias=AliasChoices("reason", "alasan", "note", "description")
    )


class Filing(SymbolRow):
    filing_date: date = Field(
        validation_alias=AliasChoices("filing_date", "date", "transaction_date")
    )
    holder_name: str | None = Field(
        default=None, validation_alias=AliasChoices("holder_name", "holder", "name")
    )
    holder_type: str | None = Field(
        default=None, validation_alias=AliasChoices("holder_type", "type", "category")
    )
    transaction_type: str | None = Field(
        default=None, validation_alias=AliasChoices("transaction_type", "action", "side")
    )
    shares: int | None = Field(
        default=None, validation_alias=AliasChoices("shares", "amount_transaction", "volume")
    )
    price: float | None = None


# ── Tier 2 ──────────────────────────────────────────────────────────────────
class DailyTransaction(SymbolRow):
    trade_date: date = Field(validation_alias=AliasChoices("trade_date", "date"))
    close_price: float | None = Field(
        default=None, validation_alias=AliasChoices("close_price", "close", "price")
    )
    volume: int | None = None
    market_cap: int | None = Field(
        default=None, validation_alias=AliasChoices("market_cap", "market_capitalization")
    )


class BrokerSummary(SymbolRow):
    trade_date: date = Field(validation_alias=AliasChoices("trade_date", "date"))
    broker_code: str = Field(validation_alias=AliasChoices("broker_code", "broker", "code"))
    net_value: float | None = Field(
        default=None, validation_alias=AliasChoices("net_value", "net", "net_amount")
    )
    buy_value: float | None = Field(
        default=None, validation_alias=AliasChoices("buy_value", "buy", "total_buy")
    )
    sell_value: float | None = Field(
        default=None, validation_alias=AliasChoices("sell_value", "sell", "total_sell")
    )

    @field_validator("broker_code", mode="before")
    @classmethod
    def _upper(cls, v: Any) -> Any:
        return str(v).strip().upper() if v is not None else v


class ForeignFlow(SymbolRow):
    trade_date: date = Field(validation_alias=AliasChoices("trade_date", "date"))
    net_value: float | None = Field(
        default=None,
        validation_alias=AliasChoices("net_value", "foreign_net", "net", "foreign_net_buy"),
    )


class FreeFloat(SymbolRow):
    free_float_pct: float | None = Field(
        default=None,
        validation_alias=AliasChoices("free_float_pct", "free_float", "percentage", "pct"),
    )
    as_of: date | None = Field(default=None, validation_alias=AliasChoices("as_of", "date"))

    @field_validator("free_float_pct", mode="after")
    @classmethod
    def _fraction(cls, v: float | None) -> float | None:
        """Terima 62 maupun 0.62; simpan selalu sebagai pecahan 0–1.

        Ambang 1.0 aman: free float 100% mustahil (selalu ada pemegang pengendali),
        dan free float 0,5% akan dikirim API sebagai 0.5, bukan 0.005.
        """
        if v is None:
            return None
        return v / 100.0 if v > 1.0 else v


class CorporateAction(SymbolRow):
    action_date: date = Field(validation_alias=AliasChoices("action_date", "date", "ex_date"))
    action_type: str | None = Field(
        default=None, validation_alias=AliasChoices("action_type", "type", "action")
    )
    detail: str | None = Field(
        default=None, validation_alias=AliasChoices("detail", "description", "note")
    )


class QuarterlyFinancial(SymbolRow):
    report_date: date = Field(
        validation_alias=AliasChoices("report_date", "date", "period", "quarter_date")
    )
    revenue: int | None = Field(
        default=None, validation_alias=AliasChoices("revenue", "total_revenue", "sales")
    )
    net_income: int | None = Field(
        default=None, validation_alias=AliasChoices("net_income", "earnings", "profit")
    )
    total_assets: int | None = Field(
        default=None, validation_alias=AliasChoices("total_assets", "assets")
    )


class CompanyProfile(SymbolRow):
    company_name: str | None = Field(
        default=None, validation_alias=AliasChoices("company_name", "name", "nama")
    )
    sub_sector: str | None = Field(
        default=None, validation_alias=AliasChoices("sub_sector", "subsector", "sector")
    )
    market_cap: int | None = Field(
        default=None, validation_alias=AliasChoices("market_cap", "market_capitalization")
    )
    listing_date: date | None = Field(
        default=None, validation_alias=AliasChoices("listing_date", "ipo_date", "listing")
    )


class Shareholder(SymbolRow):
    holder_name: str | None = Field(
        default=None, validation_alias=AliasChoices("holder_name", "name")
    )
    share_pct: float | None = Field(
        default=None, validation_alias=AliasChoices("share_pct", "percentage", "share_percentage")
    )


# Peta endpoint → model baris. Dipakai client untuk memvalidasi otomatis.
ROW_MODELS: dict[str, type[Row]] = {
    "fetch-close": ClosePrice,
    "fetch-most-traded-stocks": MostTraded,
    "fetch-companies-top-changes": TopChange,
    "fetch-suspensions": Suspension,
    "fetch-filings": Filing,
    "fetch-daily-transaction": DailyTransaction,
    "fetch-broker-summary-top": BrokerSummary,
    "fetch-broker-summary": BrokerSummary,
    "fetch-foreign-flow": ForeignFlow,
    "fetch-free-float": FreeFloat,
    "fetch-company-report": CompanyProfile,
    "fetch-quarterly-financials": QuarterlyFinancial,
    "fetch-corporate-actions": CorporateAction,
    "fetch-shareholders-composition": Shareholder,
    "fetch-companies-by-subsector": CompanyProfile,
}

# Kunci pembungkus yang lazim dipakai API: {"data": [...]} dan sejenisnya.
_ENVELOPE_KEYS = ("data", "results", "items", "rows", "records")


def unwrap(payload: Any) -> list[dict]:
    """Kupas pembungkus respons jadi daftar baris.

    Menerima list, {"data": [...]}, dan objek tunggal. Bentuk lain ditolak di
    parse_rows() dengan pesan yang menyebut bentuk apa yang datang.
    """
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in _ENVELOPE_KEYS:
            inner = payload.get(key)
            if isinstance(inner, list):
                return [r for r in inner if isinstance(r, dict)]
            if isinstance(inner, dict):
                return [inner]
        return [payload]
    return []


def preview(payload: Any, limit: int = 220) -> str:
    """Cuplikan payload untuk pesan error. Dipendekkan, tidak pernah memuat kunci API."""
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = repr(payload)
    return text[:limit] + ("…" if len(text) > limit else "")


def parse_rows[T: Row](endpoint: str, payload: Any, model: type[T] | None = None) -> list[T]:
    """Payload mentah → baris tervalidasi, atau SchemaError yang menyebut sebabnya.

    Ini satu-satunya pintu dari JSON mentah ke kode kita. Tidak ada probe yang
    boleh mengindeks dict respons langsung.
    """
    row_model = model or ROW_MODELS.get(endpoint)
    if row_model is None:
        raise SchemaError(endpoint, "tidak ada model baris terdaftar", preview(payload))

    if isinstance(payload, dict) and (payload.get("error") or payload.get("detail")):
        detail = payload.get("error") or payload.get("detail")
        raise SchemaError(endpoint, f"API mengembalikan galat: {detail}", preview(payload))

    raw = unwrap(payload)
    if not raw:
        kind = type(payload).__name__
        raise SchemaError(endpoint, f"tidak ada baris yang bisa dibaca (payload {kind})",
                          preview(payload))

    out: list[T] = []
    for i, row in enumerate(raw):
        try:
            out.append(row_model.model_validate(row))
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first.get("loc", ())) or "?"
            raise SchemaError(
                endpoint,
                f"baris {i} gagal validasi pada field '{loc}': {first.get('msg')}",
                preview(row),
            ) from exc
    return out
