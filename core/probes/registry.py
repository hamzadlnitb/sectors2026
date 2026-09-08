"""Registry probe — definisi tool yang diekspos ke LLM. Melco → Hamzah.

Perencana tidak pernah melihat endpoint Sectors mentah. Yang ia lihat adalah
enam alat milik kita, **beserta harga kreditnya**, dan ia memilih di bawah pagu
anggaran. Pemilihan alat yang sadar biaya itulah yang jadi Angka 2 di
ARCHITECTURE §6 — bukan sekadar "ada LLM di dalamnya". [AD-7]

Harga di sini tidak ditulis tangan: ia dijumlahkan dari tabel perutean, jadi
begitu spike F0 mengganti biaya asumsi dengan biaya terukur, katalog perencana
ikut berubah tanpa ada yang mengedit dua tempat.

    from core.probes.registry import PROBES, catalog
    PROBES["volume_anomaly"].run("FIXB", ctx)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import PROBE_TO_COMPONENT, ProbeName, ToolCatalogEntry  # noqa: E402
from core.probes.base import BaseProbe  # noqa: E402
from core.probes.broker import BrokerConcentrationProbe  # noqa: E402
from core.probes.foreign import ForeignFlowProbe  # noqa: E402
from core.probes.freefloat import FreeFloatProbe  # noqa: E402
from core.probes.fundamental import PriceFundamentalProbe  # noqa: E402
from core.probes.structural import StructuralProbe  # noqa: E402
from core.probes.volume import VolumeAnomalyProbe  # noqa: E402

PROBES: dict[str, BaseProbe] = {
    p.name: p for p in (
        BrokerConcentrationProbe(),
        VolumeAnomalyProbe(),
        PriceFundamentalProbe(),
        FreeFloatProbe(),
        ForeignFlowProbe(),
        StructuralProbe(),
    )
}

# Deskripsi yang dibaca LLM. Ditulis sebagai jawaban atas satu pertanyaan,
# bukan sebagai nama fungsi — perencana memilih berdasarkan pertanyaan apa yang
# ingin ia jawab tentang saham ini hari ini.
DESCRIPTIONS: dict[str, str] = {
    "broker_concentration":
        "Berapa persen net buy saham ini dikuasai 3 broker teratas dalam 20 hari bursa "
        "terakhir, dan seberapa terpusat sebarannya (HHI). Pakai saat volume tidak wajar "
        "dan perlu tahu apakah segelintir pihak yang mengumpulkan. Probe termahal.",
    "volume_anomaly":
        "Volume hari bursa terakhir berapa sigma di atas baseline 90 hari (z-score robust). "
        "Probe termurah dan paling umum jadi langkah pertama.",
    "price_fundamental":
        "Selisih return 90 hari bursa terhadap pertumbuhan laba bersih year-on-year. "
        "Pakai saat harga naik tajam dan perlu tahu apakah fundamentalnya ikut bergerak.",
    "free_float":
        "Persentase saham yang benar-benar beredar. Murah dan sering menentukan: float "
        "sangat kecil berarti harga bisa digerakkan dengan modal jauh lebih sedikit.",
    "foreign_flow":
        "Arus asing bersih 30 hari bursa dinormalkan terhadap nilai transaksi, disilangkan "
        "dengan arah harga. Pakai untuk menguji hipotesis distribusi ke ritel.",
    "structural":
        "Riwayat suspensi 24 bulan, transaksi jual insider 90 hari, dan rights issue / "
        "private placement. Pakai saat sinyal pasar sudah kuat dan perlu konteks korporasi.",
}

ARGS_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string", "pattern": "^[A-Z]{4}$",
                   "description": "Ticker IDX 4 huruf, tanpa sufiks .JK"},
    },
    "required": ["symbol"],
}


def catalog() -> list[ToolCatalogEntry]:
    """Katalog enam probe untuk perencana, berikut harga kreditnya.

    transport diisi 'rest' bukan karena probe memanggil REST langsung, tapi
    karena ToolCatalogEntry hanya mengenal dua nilai dan probe adalah alat lokal
    kita — jalur jaringan sebenarnya ditentukan tabel perutean per endpoint,
    bukan per probe. Katalog transport MCP yang sesungguhnya ada di
    core/sectors/catalog.py.
    """
    return [
        ToolCatalogEntry(
            name=f"probe_{name}",
            transport="rest",
            description=DESCRIPTIONS[name],
            args_schema=ARGS_SCHEMA,
            credit_cost=min(3, probe.cost_estimate("XXXX")),
        )
        for name, probe in PROBES.items()
    ]


def cost_table() -> dict[str, int]:
    """Biaya terburuk tiap probe. Dipakai perencana untuk menganggarkan dan
    penilai untuk menghitung baseline_credits (biaya kalau keenamnya jalan)."""
    return {name: probe.cost_estimate("XXXX") for name, probe in PROBES.items()}


def baseline_credits() -> int:
    """Biaya investigasi menyeluruh — pembanding klaim penghematan agen.

    Ini angka yang masuk ke InvestigationTranscript.baseline_credits dan jadi
    penyebut Angka 2. ARCHITECTURE §6.
    """
    return sum(cost_table().values())


def component_of(name: ProbeName) -> str:
    return PROBE_TO_COMPONENT[name]


def describe() -> str:
    lines = [f"{'probe':<24} {'komponen':<10} {'kredit':>7}  endpoint"]
    for name, probe in PROBES.items():
        lines.append(
            f"{name:<24} {component_of(name):<10} {probe.cost_estimate('XXXX'):>7}  "
            f"{', '.join(probe.endpoints)}"
        )
    lines.append(f"\ninvestigasi menyeluruh = {baseline_credits()} kredit")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
