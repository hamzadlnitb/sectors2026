# PANTAU — satu pintu untuk semua perintah. Dijalankan CI dan juri.
#
# Yang butuh API key ditandai [KEY]. Sisanya jalan di mesin bersih tanpa
# kredensial apa pun — itu syarat AD-2, bukan kenyamanan.

# python3 di Linux/CI, python di Windows. Override: make PY=python3.12
PY ?= $(shell command -v python3 2>/dev/null || echo python)

# Konsol Windows bawaan cp1252 dan keluaran kita berbahasa Indonesia dengan
# simbol sigma. Tanpa ini, target di bawah mati dengan UnicodeEncodeError.
export PYTHONIOENCODING = utf-8

.DEFAULT_GOAL := help
.PHONY: help setup demo pipeline backfill spike mcp-catalog credits \
        test lint vocab check-contracts fixtures warehouse-mini docs ci probes

help:  ## Daftar perintah
	@echo "PANTAU — perintah yang tersedia"
	@echo ""
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  [KEY] = butuh SECTORS_API_KEY di .env"

setup:  ## Pasang dependensi
	$(PY) -m pip install -r requirements.txt

# ── jalan tanpa API key ─────────────────────────────────────────────────────
demo:  ## Enam probe atas warehouse yang di-commit — nol jaringan, nol kredit
	$(PY) -m core.probes.demo

probes:  ## Daftar probe + biaya kredit yang dilihat perencana
	$(PY) -m core.probes.registry

credits:  ## Posisi kredit dari data/credit_ledger.jsonl
	$(PY) -m core.sectors.ledger

warehouse-mini:  ## Bangkitkan ulang fixtures/warehouse-mini (seed tetap)
	$(PY) fixtures/warehouse-mini/generate.py

fixtures:  ## Bangkitkan ulang fixture transkrip
	$(PY) fixtures/generate.py
	$(PY) contracts/check.py

docs:  ## Bangkitkan docs/endpoint-costs.md dan docs/mcp-catalog.md
	$(PY) tools/gen_docs.py

# ── kualitas — sama persis dengan yang dijalankan CI ────────────────────────
test:  ## Unit test: gateway kredit, warehouse, enam probe, point-in-time
	$(PY) -m pytest

lint:  ## ruff
	$(PY) -m ruff check .

vocab:  ## Larangan kosakata saran finansial, termasuk narasi LLM tersimpan [K5]
	$(PY) tools/vocab_guard.py

check-contracts:  ## Fixture wajib cocok dengan contracts/schemas.py
	$(PY) contracts/check.py

ci: lint check-contracts vocab test  ## Semua gerbang CI, berurutan

# ── butuh API key ───────────────────────────────────────────────────────────
pipeline:  ## [KEY] Sapuan Tier-1 harian + watchlist (±5 kredit)
	$(PY) -m core.ingest.tier1_market

backfill:  ## [KEY] Tarikan historis untuk kalibrasi. JALANKAN --dry-run DULU
	$(PY) -m core.ingest.backfill --dry-run

spike:  ## [KEY] Verifikasi endpoint F0 + ukur biaya aktual (maks 40 kredit)
	$(PY) spikes/run_spike.py

mcp-catalog:  ## [KEY] Tarik katalog tool MCP, perbarui docs/mcp-catalog.md
	$(PY) -c "from core.sectors import catalog; catalog.save_dump(catalog.mcp_tools())"
	$(PY) tools/gen_docs.py
