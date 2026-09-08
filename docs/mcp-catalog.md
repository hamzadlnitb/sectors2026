<!-- DIBANGKITKAN oleh tools/gen_docs.py — jangan diedit tangan. Ubah core/sectors/routing.py lalu jalankan: make docs -->

# Katalog tool MCP Sectors

Server: `https://sectors-mcp.supertype.ai/mcp` · transport Streamable HTTP · klien **tulis sendiri** di [`core/sectors/transport_mcp.py`](../core/sectors/transport_mcp.py).

Kenapa kliennya ditulis sendiri dan bukan memakai klien jadi: klien jadi tidak bisa dicegat. Dengan klien sendiri, tiap tool call MCP melewati `CreditAwareClient` yang sama persis seperti REST — pagu diperiksa, ledger dicatat, cache dipakai. `[AD-7]`

Ditarik dari server: **66 tool**. Yang dipakai PANTAU: **15**.

## Endpoint yang kami rutekan lewat MCP

Pembagian transport ditentukan **tabel per-endpoint, bukan LLM**. Perencana memilih *alat*; tabel memilih *jalur*.

| Tool MCP | Endpoint kami | Kredit | Transport utama | Ada di server? |
| --- | --- | ---: | --- | --- |
| `fetch-close` | `fetch-close` | 1 | mcp | ya |
| `fetch-companies-top-changes` | `fetch-companies-top-changes` | 1 | rest | ya |
| `fetch-filings` | `fetch-filings` | 1 | rest | ya |
| `fetch-most-traded-stocks` | `fetch-most-traded-stocks` | 2 | rest | ya |
| `fetch-suspensions` | `fetch-suspensions` | 1 | rest | ya |
| `fetch-broker-summary` | `fetch-broker-summary` | 1 | mcp | ya |
| `fetch-broker-summary-top` | `fetch-broker-summary-top` | 2 | mcp | ya |
| `fetch-companies-by-subsector` | `fetch-companies-by-subsector` | 1 | mcp | ya |
| `fetch-company-report` | `fetch-company-report` | 2 | rest | ya |
| `fetch-corporate-actions` | `fetch-corporate-actions` | 1 | mcp | ya |
| `fetch-daily-transaction` | `fetch-daily-transaction` | 1 | rest | ya |
| `fetch-foreign-flow` | `fetch-foreign-flow` | 1 | rest | ya |
| `fetch-free-float` | `fetch-free-float` | 1 | mcp | ya |
| `fetch-quarterly-financials` | `fetch-quarterly-financials` | 1 | mcp | ya |
| `fetch-shareholders-composition` | `fetch-shareholders-composition` | 1 | mcp | ya |

## MCP vs REST untuk endpoint yang sama

Biaya kreditnya sama — yang berbeda adalah ongkos rekayasa dan ketersediaan. Endpoint dua jalur otomatis punya fallback: MCP mati → REST, tanpa menjatuhkan pipeline (`tests/sectors/test_client.py`).

| Endpoint | REST | MCP | Dipakai | Alasan |
| --- | --- | --- | --- | --- |
| `fetch-close` | `/daily/close/` | `fetch-close` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-companies-top-changes` | `/companies/top-changes/` | `fetch-companies-top-changes` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-filings` | `/filings/` | `fetch-filings` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-most-traded-stocks` | `/most-traded/` | `fetch-most-traded-stocks` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-suspensions` | `/suspensions/` | `fetch-suspensions` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-broker-summary` | — | `fetch-broker-summary` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-broker-summary-top` | `/broker-summary-top/{symbol}/` | `fetch-broker-summary-top` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-companies-by-subsector` | — | `fetch-companies-by-subsector` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-company-report` | `/company/report/{symbol}/` | `fetch-company-report` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-corporate-actions` | — | `fetch-corporate-actions` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-daily-transaction` | `/daily/{symbol}/` | `fetch-daily-transaction` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-foreign-flow` | `/foreign-flow/{symbol}/` | `fetch-foreign-flow` | rest | sapuan massal butuh panggilan presisi & batched |
| `fetch-free-float` | — | `fetch-free-float` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-quarterly-financials` | — | `fetch-quarterly-financials` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |
| `fetch-shareholders-composition` | — | `fetch-shareholders-composition` | mcp | ekor panjang tool spesialis; tidak perlu wrapper REST tulisan tangan |

## Tool server yang tidak kami pakai

51 tool tersedia tapi tidak dipakai. Dicantumkan dengan sengaja: memakai sedikit tool secara sadar lebih jujur daripada mengaku memakai semuanya.

```
fetch-broker-activity
fetch-broker-activity-top
fetch-brokers
fetch-companies-quarterly-financial-dates
fetch-companies-with-segments
fetch-company-segments
fetch-idx-market-cap
fetch-index-daily
fetch-industries
fetch-klse-companies-by-sector
fetch-klse-company-report
fetch-klse-sectors
fetch-klse-top-companies
fetch-listing-performance
fetch-mining-commodities
fetch-mining-commodity-price
fetch-mining-companies
fetch-mining-company-detail
fetch-mining-company-financials
fetch-mining-company-ownership
fetch-mining-company-performance
fetch-mining-contracts
fetch-mining-exports
fetch-mining-global-commodity
fetch-mining-license-auction-detail
fetch-mining-license-auctions
fetch-mining-licenses
fetch-mining-resources-reserves
fetch-mining-resources-reserves-detail
fetch-mining-sales-destination
fetch-mining-site-detail
fetch-mining-sites
fetch-mining-total-production
fetch-news
fetch-quarterly-financial-dates
fetch-sgx-buybacks
fetch-sgx-companies-by-sector
fetch-sgx-company-report
fetch-sgx-daily-transaction
fetch-sgx-filings
fetch-sgx-news
fetch-sgx-sectors
fetch-sgx-short-sell
fetch-sgx-subsectors
fetch-sgx-tags
fetch-sgx-top-companies
fetch-subindustries
fetch-subsector-report
fetch-tags
fetch-top-brokers
get-subsectors
```

---
_Dibangkitkan 2026-09-08 oleh `make docs`._
