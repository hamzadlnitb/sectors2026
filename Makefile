.PHONY: check-contracts fixtures

## Validasi: fixture wajib cocok dengan kontrak. Dijalankan CI.
check-contracts:
	python3 contracts/check.py

## Bangkitkan ulang fixture dari contracts/schemas.py
fixtures:
	python3 fixtures/generate.py
	python3 contracts/check.py

# Target berikut diisi Melco di fase M6:
#   demo · pipeline · credits · test · investigate
