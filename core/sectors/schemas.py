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


def _as_date(value: Any) -> Any:
    """Ambil bagian tanggal dari stempel waktu ISO.

    fetch-filings mengirim "2026-09-07T19:36:14" untuk field yang di kontrak
    bertipe DATE. Membiarkannya berarti tiap filing ditolak validator, dan
    probe SSS kehilangan seluruh sinyal insider. Jamnya sengaja dibuang: data
    Sectors EOD, jadi presisi jam tidak berarti apa-apa dan hanya akan bikin
    kunci primer warehouse meleset. [K7]
    """
    if isinstance(value, str) and "T" in value:
        return value.split("T", 1)[0]
    return value


class Row(BaseModel):
    """Induk semua baris respons. Longgar terhadap kolom tambahan, ketat pada isi."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @field_validator("*", mode="before")
    @classmethod
    def _potong_stempel_waktu(cls, v: Any, info) -> Any:
        if info.field_name and info.field_name.endswith(("_date", "as_of")):
            return _as_date(v)
        return v


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
        default=None,
        validation_alias=AliasChoices("last_close_price", "last_close", "close", "price"),
    )
    trade_date: date | None = Field(
        default=None, validation_alias=AliasChoices("latest_close_date", "trade_date", "date")
    )
    direction: str | None = None
    """'top_gainers' atau 'top_losers' — diturunkan adapter dari bentuk bersarangnya."""


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
        validation_alias=AliasChoices("filing_date", "timestamp", "date", "transaction_date")
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
        default=None,
        validation_alias=AliasChoices("net_idr", "net_value", "net", "net_amount"),
    )
    buy_value: float | None = Field(
        default=None,
        validation_alias=AliasChoices("buy_idr", "buy_value", "buy", "total_buy"),
    )
    sell_value: float | None = Field(
        default=None,
        validation_alias=AliasChoices("sell_idr", "sell_value", "sell", "total_sell"),
    )

    @field_validator("broker_code", mode="before")
    @classmethod
    def _upper(cls, v: Any) -> Any:
        return str(v).strip().upper() if v is not None else v


class ForeignFlow(SymbolRow):
    trade_date: date = Field(validation_alias=AliasChoices("trade_date", "date"))
    net_value: float | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "net_foreign_inflow", "net_value", "foreign_net", "net", "foreign_net_buy"
        ),
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

# Konteks yang hidup di LEVEL PEMBUNGKUS dan harus diturunkan ke tiap baris.
# fetch-foreign-flow adalah alasannya: barisnya cuma {date, net_foreign_inflow},
# sementara symbol-nya ada sekali di atas. Tanpa penurunan ini, tiap baris arus
# asing kehilangan identitas emitennya.
_ENVELOPE_CONTEXT = ("symbol", "ticker")


def unwrap(payload: Any) -> list[dict]:
    """Kupas pembungkus respons jadi daftar baris.

    Menerima list, {"data": [...]}, dan objek tunggal. Konteks di level
    pembungkus diturunkan ke tiap baris; baris menang kalau kuncinya bentrok.
    """
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        konteks = {k: payload[k] for k in _ENVELOPE_CONTEXT if k in payload}
        for key in _ENVELOPE_KEYS:
            inner = payload.get(key)
            if isinstance(inner, list):
                return [{**konteks, **r} for r in inner if isinstance(r, dict)]
            if isinstance(inner, dict):
                return [{**konteks, **inner}]
        return [payload]
    return []


# ── Adapter bentuk per endpoint ─────────────────────────────────────────────
# Spike F0 membuktikan Sectors memakai EMPAT bentuk respons yang berbeda, bukan
# satu. Memaksakan satu unwrap generik untuk semuanya berarti tiga di antaranya
# diam-diam salah baca. Tiap adapter di bawah punya padanannya di spikes/raw/,
# dan tests/sectors/test_respons_asli.py menjalankannya atas berkas itu.

def _flatten_keyed_by_date(payload: Any) -> list[dict]:
    """{"2026-08-10": [...], "2026-08-11": [...]} → baris ber-'date'.

    Bentuk fetch-most-traded-stocks. Tanggalnya ada di KUNCI, bukan di baris,
    jadi tanpa penurunan ini seluruh riwayat menumpuk di satu tanggal.
    """
    if not isinstance(payload, dict):
        return unwrap(payload)
    keluar: list[dict] = []
    for tanggal, baris in payload.items():
        if isinstance(baris, list):
            keluar += [{"date": tanggal, **r} for r in baris if isinstance(r, dict)]
    return keluar


def _flatten_top_changes(payload: Any) -> list[dict]:
    """{"top_gainers": {"1d": [...]}, "top_losers": {"1d": [...]}} → baris rata.

    Arah pergerakan ikut dibawa sebagai 'direction': penyaring kandidat perlu
    membedakan yang naik dari yang turun, dan itu hilang kalau digabung buta.
    """
    if not isinstance(payload, dict):
        return unwrap(payload)
    keluar: list[dict] = []
    for arah in ("top_gainers", "top_losers"):
        per_periode = payload.get(arah)
        if not isinstance(per_periode, dict):
            continue
        for periode, baris in per_periode.items():
            if isinstance(baris, list):
                keluar += [{"direction": arah, "period": periode, **r}
                           for r in baris if isinstance(r, dict)]
    return keluar


def _flatten_company_report(payload: Any) -> list[dict]:
    """Laporan emiten bersarang → satu baris profil rata.

    Hanya bagian yang dipakai warehouse yang diambil. Sisanya (dividend,
    management, peers, future) sengaja dibuang: menyimpan seluruh laporan
    berarti menyimpan 100 KB per emiten untuk lima kolom yang terpakai.
    """
    if not isinstance(payload, dict):
        return unwrap(payload)
    overview = payload.get("overview") or {}
    baris = {
        "symbol": payload.get("symbol"),
        "company_name": payload.get("company_name"),
        "sub_sector": overview.get("sub_sector") or overview.get("sub_industry"),
        "market_cap": overview.get("market_cap"),
        "listing_date": overview.get("listing_date"),
    }
    return [{k: v for k, v in baris.items() if v is not None}]


def _flatten_broker_top(payload: Any) -> list[dict]:
    """{symbol, start, end, top_buyers: [...], top_sellers: [...]} -> baris broker.

    Responsnya AGREGAT sepanjang periode, bukan rincian per hari bursa — tidak
    ada trade_date di baris mana pun. Tanggal akhir periode dipakai sebagai
    trade_date: itu pernyataan yang jujur ("posisi bersih broker per tanggal
    ini"), dan BCI memang menjumlahkan sepanjang jendela, jadi tidak ada
    informasi yang hilang.
    """
    if not isinstance(payload, dict):
        return unwrap(payload)
    konteks = {"symbol": payload.get("symbol"), "trade_date": payload.get("end")}
    keluar: list[dict] = []
    for sisi in ("top_buyers", "top_sellers"):
        for r in payload.get(sisi) or []:
            if isinstance(r, dict):
                keluar.append({**konteks, "side": sisi, **r})
    return keluar


# Jenis aksi korporasi -> nama kolom tanggalnya. Tiap jenis memakai nama
# sendiri, jadi tidak ada satu alias yang menutup semuanya.
_TANGGAL_AKSI = {
    "agm": "agm_date", "bonus": "payment_date", "dividend": "ex_date",
    "right_issue": "ex_date", "stock_split": "date", "warrant": "ex_date",
    "upcoming_dividend": "ex_date",
}


def _flatten_corporate_actions(payload: Any) -> list[dict]:
    """{symbol, corporate_actions: {agm: [...], right_issue: [...]}} -> baris rata.

    Jenis aksinya jadi action_type — itu yang dibaca probe SSS untuk mengenali
    rights issue dan private placement.
    """
    if not isinstance(payload, dict):
        return unwrap(payload)
    symbol = payload.get("symbol")
    blok = payload.get("corporate_actions")
    if not isinstance(blok, dict):
        return unwrap(payload)

    keluar: list[dict] = []
    for tipe, baris in blok.items():
        kolom = _TANGGAL_AKSI.get(tipe, "ex_date")
        for r in baris or []:
            if not isinstance(r, dict):
                continue
            tanggal = r.get(kolom) or r.get("ex_date") or r.get("date")
            if not tanggal:
                continue  # aksi tanpa tanggal tidak bisa dipakai point-in-time
            rincian = {k: v for k, v in r.items() if v not in (None, "")}
            keluar.append({
                "symbol": symbol, "action_date": tanggal, "action_type": tipe,
                "detail": json.dumps(rincian, ensure_ascii=False)[:400],
            })
    return keluar


SHAPES: dict[str, Any] = {
    "fetch-broker-summary-top": _flatten_broker_top,
    "fetch-corporate-actions": _flatten_corporate_actions,
    "fetch-most-traded-stocks": _flatten_keyed_by_date,
    "fetch-companies-top-changes": _flatten_top_changes,
    "fetch-company-report": _flatten_company_report,
}


def flatten(endpoint: str, payload: Any) -> list[dict]:
    """Payload mentah → daftar baris rata, sesuai bentuk asli endpoint ini."""
    return SHAPES.get(endpoint, unwrap)(payload)


def _memang_kosong(payload: Any) -> bool:
    """True kalau payload secara eksplisit menyatakan dirinya kosong."""
    if isinstance(payload, list):
        return True
    if not isinstance(payload, dict):
        return False
    blok = payload.get("pagination")
    if isinstance(blok, dict) and blok.get("total_count") == 0:
        return True
    return any(isinstance(payload.get(k), list) and not payload[k] for k in _ENVELOPE_KEYS)


def pagination_of(payload: Any) -> dict | None:
    """Blok paginasi kalau ada.

    Penting untuk anggaran: fetch-suspensions mengembalikan 20 baris per
    panggilan dari total 533. Backfill yang mengabaikan ini akan mengira sudah
    menarik 24 bulan padahal baru satu halaman. Lihat docs/endpoint-costs.md.
    """
    if isinstance(payload, dict):
        blok = payload.get("pagination")
        if isinstance(blok, dict):
            return blok
    return None


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

    raw = flatten(endpoint, payload)
    if not raw:
        # Nol baris bisa berarti dua hal yang sangat berbeda, dan cuma satu di
        # antaranya kesalahan. Pembungkus yang menyatakan dirinya kosong
        # ("results": [], total_count 0) adalah JAWABAN YANG SAH — hari bursa
        # tanpa suspensi memang begitu, dan memperlakukannya sebagai galat
        # membuat cron harian merah tiap kali pasar tenang. Yang benar-benar
        # salah adalah payload yang bentuknya tidak dikenali sama sekali.
        if _memang_kosong(payload):
            return []
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
