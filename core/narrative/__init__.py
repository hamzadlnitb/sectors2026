"""Narasi putusan: prosa LLM yang dipagari validator sitasi. [AD-4]

Dua pintu keluar saja, keduanya aman:

    from core.narrative import narrate, unsupported_numbers

`narrate()` selalu mengembalikan teks yang sudah lolos validator — kalau LLM
mengarang angka atau mati, yang keluar template deterministik. Pemanggil tidak
pernah perlu memeriksa ulang.
"""

from __future__ import annotations

from core.narrative.generate import narrate
from core.narrative.validate import unsupported_numbers

__all__ = ["narrate", "unsupported_numbers"]
