"""Warehouse DuckDB + Parquet: tulis dari ingest, baca point-in-time dari probe.

Skema tabel TIDAK ditulis ulang di sini — DDL-nya diambil apa adanya dari
contracts/warehouse.sql, kontrak beku yang juga dibaca Hamzah. Satu sumber
kebenaran; kalau DDL berubah, penulis ikut berubah tanpa ada yang mengedit dua
tempat.

**Point-in-time ditegakkan struktur, bukan kedisiplinan.** connect(as_of)
memasang VIEW yang sudah tersaring "kolom tanggal ≤ as_of". Probe tidak bisa
melihat masa depan walau SQL-nya salah tulis, karena datanya memang tidak ada di
sesi itu. Ini penting bukan demi kerapian: satu probe yang membaca data setelah
as_of membocorkan lookahead ke kalibrasi bobot Hamzah, dan Angka 1 jadi bohong
tanpa ada yang sadar. [contracts/CHANGES.md C1, catatan penutup]

    from core.ingest.warehouse import Warehouse
    wh = Warehouse()
    with wh.connect(as_of=date(2026, 9, 5)) as con:
        con.sql("SELECT * FROM daily_close WHERE symbol = 'FIXA'")
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from core.sectors.redact import get_logger

log = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WAREHOUSE = ROOT / "data" / "warehouse"
DDL_PATH = ROOT / "contracts" / "warehouse.sql"


@dataclass(frozen=True)
class Table:
    """Satu tabel warehouse dan aturan point-in-time-nya."""

    name: str
    cut_column: str | None
    """Kolom yang menentukan 'kapan fakta ini boleh diketahui'. None = tidak berwaktu."""
    keys: tuple[str, ...] = ()
    """Kunci primer sesuai DDL. Kosong = tabel append, dideduplikasi dengan DISTINCT."""
    allow_null_cut: bool = False
    """True hanya untuk tabel identitas — lihat catatan di company_profile."""


TABLES: dict[str, Table] = {
    "daily_close": Table("daily_close", "trade_date", ("trade_date", "symbol")),
    "daily_transaction": Table("daily_transaction", "trade_date", ("trade_date", "symbol")),
    "broker_summary": Table("broker_summary", "trade_date",
                            ("trade_date", "symbol", "broker_code")),
    "foreign_flow": Table("foreign_flow", "trade_date", ("trade_date", "symbol")),
    "free_float": Table("free_float", "as_of", ("symbol",)),
    "suspensions": Table("suspensions", "start_date", ("symbol", "start_date")),
    "filings": Table("filings", "filing_date"),
    "corporate_actions": Table("corporate_actions", "action_date"),
    "quarterly_financials": Table("quarterly_financials", "report_date",
                                  ("symbol", "report_date")),
    # company_profile adalah tabel IDENTITAS, bukan sinyal: nama emiten dan
    # subsektor tidak membocorkan hasil. Barisnya dibiarkan lolos walau
    # listing_date kosong, supaya probe tetap bisa mengenali emiten.
    # Konsekuensinya: market_cap di sini TIDAK boleh dipakai sebagai sinyal
    # point-in-time — untuk itu ada daily_transaction.market_cap yang bertanggal.
    "company_profile": Table("company_profile", "listing_date", ("symbol",),
                             allow_null_cut=True),
}


def _ddl_statements() -> list[str]:
    """Pecah contracts/warehouse.sql jadi pernyataan, buang komentar."""
    raw = DDL_PATH.read_text(encoding="utf-8")
    raw = re.sub(r"--[^\n]*", "", raw)
    return [s.strip() for s in raw.split(";") if s.strip()]


def ddl_for(table: str) -> str:
    for stmt in _ddl_statements():
        if re.search(rf"CREATE TABLE IF NOT EXISTS\s+{table}\b", stmt, re.IGNORECASE):
            return stmt
    raise KeyError(f"tabel '{table}' tidak ada di {DDL_PATH.name}")


def columns_of(table: str) -> list[str]:
    """Nama kolom sesuai DDL kontrak, dalam urutan DDL."""
    con = duckdb.connect()
    try:
        con.execute(ddl_for(table))
        return [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
    finally:
        con.close()


class Warehouse:
    """Kumpulan parquet di satu direktori, dibaca sebagai basis data DuckDB."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_WAREHOUSE

    # ── lokasi ──────────────────────────────────────────────────────────────
    def file(self, table: str) -> Path:
        return self.path / f"{table}.parquet"

    def exists(self, table: str) -> bool:
        return self.file(table).exists()

    def available(self) -> list[str]:
        return [t for t in TABLES if self.exists(t)]

    # ── tulis ───────────────────────────────────────────────────────────────
    def write(self, table: str, rows: Iterable[Any] | pd.DataFrame) -> int:
        """Gabungkan baris baru ke parquet tabel. Yang baru menang atas yang lama.

        Menerima DataFrame atau iterable model pydantic. Mengembalikan jumlah
        baris di tabel SETELAH penggabungan, bukan jumlah yang ditambahkan —
        angka itu yang berguna di log pipeline.
        """
        spec = TABLES[table]
        df = self._to_frame(table, rows)
        target = self.file(table)
        target.parent.mkdir(parents=True, exist_ok=True)

        con = duckdb.connect()
        try:
            con.execute(ddl_for(table))
            cols = ", ".join(columns_of(table))
            if target.exists():
                con.execute(
                    f"INSERT OR REPLACE INTO {table} SELECT {cols} "
                    f"FROM read_parquet('{target.as_posix()}')"
                )
            if len(df):
                con.register("incoming", df)
                verb = "INSERT OR REPLACE" if spec.keys else "INSERT"
                con.execute(f"{verb} INTO {table} SELECT {cols} FROM incoming")

            if not spec.keys:
                # Tabel append tanpa kunci primer: dedup eksplisit, kalau tidak
                # backfill yang dijalankan dua kali akan menggandakan filings.
                con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT DISTINCT * FROM {table}")

            order = ", ".join(spec.keys) if spec.keys else cols
            con.execute(
                f"COPY (SELECT {cols} FROM {table} ORDER BY {order}) "
                f"TO '{target.as_posix()}' (FORMAT PARQUET)"
            )
            return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        finally:
            con.close()

    def _to_frame(self, table: str, rows: Iterable[Any] | pd.DataFrame) -> pd.DataFrame:
        """Model pydantic / dict → DataFrame berkolom persis DDL."""
        cols = columns_of(table)
        if isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            records = [
                r.model_dump() if hasattr(r, "model_dump") else dict(r)
                for r in rows
            ]
            df = pd.DataFrame.from_records(records)
        if df.empty:
            return pd.DataFrame({c: pd.Series(dtype="object") for c in cols})
        for missing in [c for c in cols if c not in df.columns]:
            df[missing] = None
        return df[cols]

    # ── baca ────────────────────────────────────────────────────────────────
    @contextmanager
    def connect(
        self, as_of: date | None = None, tables: Iterable[str] | None = None
    ) -> Iterator[duckdb.DuckDBPyConnection]:
        """Koneksi baca-saja. Kalau as_of diisi, tiap view tersaring ke ≤ as_of.

        Tabel yang parquet-nya belum ada tetap dibuat sebagai view kosong
        berskema DDL — supaya probe yang menanyakannya dapat "nol baris", bukan
        "Catalog Error: Table does not exist" yang harus ditangkap enam kali.
        """
        con = duckdb.connect(database=":memory:")
        try:
            for name in tables or TABLES:
                self._mount(con, name, as_of)
            yield con
        finally:
            con.close()

    def _mount(self, con: duckdb.DuckDBPyConnection, table: str, as_of: date | None) -> None:
        spec = TABLES[table]
        target = self.file(table)
        if not target.exists():
            con.execute(ddl_for(table))  # tabel kosong berskema kontrak
            return

        cols = ", ".join(columns_of(table))
        source = f"SELECT {cols} FROM read_parquet('{target.as_posix()}')"
        if as_of is not None and spec.cut_column:
            guard = f"{spec.cut_column} <= DATE '{as_of.isoformat()}'"
            if spec.allow_null_cut:
                guard = f"({spec.cut_column} IS NULL OR {guard})"
            source = f"SELECT * FROM ({source}) WHERE {guard}"
        con.execute(f"CREATE VIEW {table} AS {source}")

    def frame(self, table: str, as_of: date | None = None, where: str = "",
              params: list | None = None) -> pd.DataFrame:
        """Satu tabel sebagai DataFrame, sudah tersaring point-in-time."""
        with self.connect(as_of, tables=[table]) as con:
            sql = f"SELECT * FROM {table}"
            if where:
                sql += f" WHERE {where}"
            return con.execute(sql, params or []).df()

    # ── ringkasan ───────────────────────────────────────────────────────────
    def summary(self, as_of: date | None = None) -> list[dict]:
        """Isi warehouse per tabel. Dicetak di log cron sebagai bukti sapuan jalan."""
        out = []
        with self.connect(as_of) as con:
            for name, spec in TABLES.items():
                if not self.exists(name):
                    out.append({"table": name, "rows": 0, "first": None, "last": None})
                    continue
                rows = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                first = last = None
                if spec.cut_column and rows:
                    first, last = con.execute(
                        f"SELECT min({spec.cut_column}), max({spec.cut_column}) FROM {name}"
                    ).fetchone()
                out.append({"table": name, "rows": rows, "first": first, "last": last})
        return out

    def describe(self, as_of: date | None = None) -> str:
        lines = [f"warehouse: {self.path}"]
        for row in self.summary(as_of):
            rentang = f"  {row['first']} .. {row['last']}" if row["first"] else ""
            lines.append(f"  {row['table']:<22} {row['rows']:>8} baris{rentang}")
        return "\n".join(lines)


def trading_days(wh: Warehouse, as_of: date, lookback: int) -> list[date]:
    """Tanggal bursa yang benar-benar ADA di warehouse, mundur dari as_of.

    Kalender bursa tidak dihitung sendiri — libur nasional IDX tidak bisa
    ditebak dari hari kerja. Yang dipakai adalah tanggal yang benar-benar punya
    data close.
    """
    with wh.connect(as_of, tables=["daily_close"]) as con:
        rows = con.execute(
            "SELECT DISTINCT trade_date FROM daily_close ORDER BY trade_date DESC LIMIT ?",
            [lookback],
        ).fetchall()
    return sorted(r[0] for r in rows)
