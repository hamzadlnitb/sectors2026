-- Kontrak 4 — skema tabel warehouse DuckDB.
-- Melco menulis, Hamzah membaca. Perubahan butuh persetujuan bertiga.

CREATE TABLE IF NOT EXISTS daily_close (       -- fetch-close, 1 panggilan = seluruh IDX
    trade_date   DATE     NOT NULL,
    symbol       VARCHAR  NOT NULL,
    close_price  DOUBLE,
    PRIMARY KEY (trade_date, symbol)
);

CREATE TABLE IF NOT EXISTS daily_transaction (
    trade_date   DATE     NOT NULL,
    symbol       VARCHAR  NOT NULL,
    close_price  DOUBLE,
    volume       BIGINT,
    market_cap   HUGEINT,
    PRIMARY KEY (trade_date, symbol)
);

CREATE TABLE IF NOT EXISTS broker_summary (
    trade_date   DATE     NOT NULL,
    symbol       VARCHAR  NOT NULL,
    broker_code  VARCHAR  NOT NULL,
    net_value    DOUBLE,
    buy_value    DOUBLE,
    sell_value   DOUBLE,
    PRIMARY KEY (trade_date, symbol, broker_code)
);

CREATE TABLE IF NOT EXISTS foreign_flow (
    trade_date   DATE     NOT NULL,
    symbol       VARCHAR  NOT NULL,
    net_value    DOUBLE,
    PRIMARY KEY (trade_date, symbol)
);

CREATE TABLE IF NOT EXISTS free_float (
    symbol           VARCHAR PRIMARY KEY,
    free_float_pct   DOUBLE,
    as_of            DATE
);

CREATE TABLE IF NOT EXISTS suspensions (       -- sumber label kalibrasi
    symbol       VARCHAR  NOT NULL,
    start_date   DATE     NOT NULL,
    end_date     DATE,
    reason       VARCHAR,
    PRIMARY KEY (symbol, start_date)
);

CREATE TABLE IF NOT EXISTS filings (           -- insider trading
    filing_date      DATE     NOT NULL,
    symbol           VARCHAR  NOT NULL,
    holder_name      VARCHAR,
    holder_type      VARCHAR,
    transaction_type VARCHAR,
    shares           BIGINT,
    price            DOUBLE
);

CREATE TABLE IF NOT EXISTS corporate_actions (
    symbol       VARCHAR NOT NULL,
    action_date  DATE    NOT NULL,
    action_type  VARCHAR,
    detail       VARCHAR
);

CREATE TABLE IF NOT EXISTS quarterly_financials (
    symbol       VARCHAR NOT NULL,
    report_date  DATE    NOT NULL,
    revenue      HUGEINT,
    net_income   HUGEINT,
    total_assets HUGEINT,
    PRIMARY KEY (symbol, report_date)
);

CREATE TABLE IF NOT EXISTS company_profile (
    symbol       VARCHAR PRIMARY KEY,
    company_name VARCHAR,
    sub_sector   VARCHAR,
    market_cap   HUGEINT,
    listing_date DATE
);

-- Memori agen. Hamzah menulis dan membaca; Melco tidak menyentuh.
CREATE TABLE IF NOT EXISTS investigations (
    symbol         VARCHAR NOT NULL,
    as_of          DATE    NOT NULL,
    pantau_score   INTEGER,
    band           VARCHAR,
    confidence     DOUBLE,
    credits_total  INTEGER,
    transcript_path VARCHAR,
    PRIMARY KEY (symbol, as_of)
);
