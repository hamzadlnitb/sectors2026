"""Agen investigasi PANTAU — perencana → penyelidik → penilai.

Orkestrasi ditulis sendiri, bukan memakai framework agen pihak ketiga. Itu
disengaja: yang dinilai Track 1 justru logika ini, dan framework akan
menyembunyikannya. ARCHITECTURE §1 uji anti-diskualifikasi.

    from core.agent import investigate_symbol
    transkrip = investigate_symbol("BBCA")
"""

from core.agent.runner import investigate_symbol

__all__ = ["investigate_symbol"]
