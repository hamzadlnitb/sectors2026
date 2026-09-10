"""Skoring deterministik. Agen memutuskan APA yang diselidiki; berkas-berkas di
sini memutuskan BERAPA skornya. Tidak ada LLM di jalur ini. [AD-4][K8]"""

from core.scoring.composite import Composite, score
from core.scoring.facts import evidence_book, index

__all__ = ["Composite", "score", "evidence_book", "index"]
