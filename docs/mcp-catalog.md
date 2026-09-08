<!-- DIBANGKITKAN oleh tools/gen_docs.py — jangan diedit tangan. Ubah core/sectors/routing.py lalu jalankan: make docs -->

# Katalog tool MCP Sectors

Server: `https://sectors-mcp.supertype.ai/mcp` · transport Streamable HTTP · klien **tulis sendiri** di [`core/sectors/transport_mcp.py`](../core/sectors/transport_mcp.py).

Kenapa kliennya ditulis sendiri dan bukan memakai klien jadi: klien jadi tidak bisa dicegat. Dengan klien sendiri, tiap tool call MCP melewati `CreditAwareClient` yang sama persis seperti REST — pagu diperiksa, ledger dicatat, cache dipakai. `[AD-7]`

> ⚠️ **Katalog server belum pernah ditarik.** Butuh `SECTORS_API_KEY`; jalankan `make mcp-catalog`. Tabel di bawah adalah tool MCP yang **terdaftar di tabel perutean kita**, yaitu nama yang kita harapkan ada di server — belum dikonfirmasi.

## Endpoint yang kami rutekan lewat MCP

Pembagian transport ditentukan **tabel per-endpoint, bukan LLM**. Perencana memilih *alat*; tabel memilih *jalur*.

| Tool MCP | Endpoint kami | Kredit | Transport utama | Ada di server? |
| --- | --- | ---: | --- | --- |
| `get_daily_close` | `fetch-close` | 1 | rest | — |
| `get_top_companies_movers` | `fetch-companies-top-changes` | 1 | rest | — |
| `get_insider_trading_filings` | `fetch-filings` | 1 | rest | — |
| `get_most_traded_stocks` | `fetch-most-traded-stocks` | 1 | rest | — |
| `get_suspended_stocks` | `fetch-suspensions` | 1 | rest | — |
| `get_broker_summary` | `fetch-broker-summary` | 2 | mcp | — |
| `get_top_brokers` | `fetch-broker-summary-top` | 3 | rest | — |
| `get_companies_by_subsector` | `fetch-companies-by-subsector` | 1 | mcp | — |
| `get_company_report` | `fetch-company-report` | 2 | rest | — |
| `get_corporate_actions` | `fetch-corporate-actions` | 2 | mcp | — |
| `get_daily_transaction` | `fetch-daily-transaction` | 1 | rest | — |
| `get_foreign_flow` | `fetch-foreign-flow` | 2 | rest | — |
| `get_free_float` | `fetch-free-float` | 1 | mcp | — |
| `get_quarterly_financials` | `fetch-quarterly-financials` | 2 | mcp | — |
| `get_shareholders` | `fetch-shareholders-composition` | 2 | mcp | — |

## MCP vs REST untuk endpoint yang sama

Biaya kreditnya sama — yang berbeda adalah ongkos rekayasa dan ketersediaan. Endpoint dua jalur otomatis punya fallback: MCP mati → REST, tanpa menjatuhkan pipeline (`tests/sectors/test_client.py`).

| Endpoint | REST | MCP | Dipakai | Alasan |
| --- | --- | --- | --- | --- |
| `fetch-close` | `/daily/close/` | `get_daily_close` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-companies-top-changes` | `/companies/top-changes/` | `get_top_companies_movers` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-filings` | `/filings/` | `get_insider_trading_filings` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-most-traded-stocks` | `/most-traded/` | `get_most_traded_stocks` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-suspensions` | `/suspensions/` | `get_suspended_stocks` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-broker-summary` | — | `get_broker_summary` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-broker-summary-top` | `/broker-summary-top/{symbol}/` | `get_top_brokers` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-companies-by-subsector` | — | `get_companies_by_subsector` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-company-report` | `/company/report/{symbol}/` | `get_company_report` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-corporate-actions` | — | `get_corporate_actions` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-daily-transaction` | `/daily/{symbol}/` | `get_daily_transaction` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-foreign-flow` | `/foreign-flow/{symbol}/` | `get_foreign_flow` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-free-float` | — | `get_free_float` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-quarterly-financials` | — | `get_quarterly_financials` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-shareholders-composition` | — | `get_shareholders` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |

---
_Dibangkitkan 2026-09-08 oleh `make docs`._
