"""Probe palsu supaya Hamzah lepas landas tanpa menunggu probe asli. [TASK.md kickoff]

Bukan darurat — ini cara kerja yang sah sampai probe asli diserahkan satu per
satu. Stub memenuhi Protocol Probe yang persis sama (`name`, `cost_estimate`,
`run`), jadi mengganti stub dengan probe asli cukup dengan menukar registry:

    from core.probes.registry import PROBES          # asli, butuh warehouse
    from core.probes.stubs import STUB_PROBES        # palsu, jalan di mana saja

Tiga hal yang sengaja dijaga:

1. **Deterministik.** Ticker yang sama selalu memberi hasil yang sama, supaya
   tes agen tidak jadi flaky karena lapisan yang bukan sedang diuji.
2. **Bentuk lengkap.** Bukti berisi EvidenceEntry sungguhan yang lolos validator
   sitasi, bukan string kosong — kalau tidak, pagar Hamzah akan lolos di stub
   lalu jebol di data asli.
3. **Kasus tepi ikut ada.** `FIXD` mengembalikan sub_score None dengan alasan,
   supaya jalur "komponen tidak tersedia" ikut terlatih sejak awal.

Biaya kredit stub SELALU 0 — ia tidak menyentuh jaringan. Yang mengikuti probe
asli adalah `cost_estimate()`, karena angka itulah yang dipakai perencana untuk
menganggarkan.
"""

from __future__ import annotations

import sys
from datetime import date
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import EvidenceEntry, ProbeName, ProbeResult  # noqa: E402
from core.probes.base import Context, stamp  # noqa: E402
from core.probes.registry import PROBES  # noqa: E402

STUB_AS_OF = date(2026, 9, 4)  # hari bursa terakhir di fixtures/warehouse-mini

# Profil bawaan sesuai tiga fixture transkrip yang sudah beku.
PROFILES: dict[str, dict[str, float | None]] = {
    "FIXA": {"volume_anomaly": 8.0, "broker_concentration": 12.0, "price_fundamental": 5.0,
             "free_float": 0.0, "foreign_flow": 0.0, "structural": 0.0},
    "FIXB": {"volume_anomaly": 74.0, "broker_concentration": 65.0, "price_fundamental": 60.0,
             "free_float": 49.0, "foreign_flow": 39.0, "structural": 30.0},
    "FIXC": {"volume_anomaly": 92.0, "broker_concentration": 91.0, "price_fundamental": 19.0,
             "free_float": 100.0, "foreign_flow": 85.0, "structural": 89.0},
    # IPO baru: sebagian besar probe menyerah. Jalur "tidak tersedia" wajib
    # terlatih sejak awal, bukan ditemukan saat penyambungan 18 Sep.
    "FIXD": {"volume_anomaly": None, "broker_concentration": None, "price_fundamental": None,
             "free_float": 33.0, "foreign_flow": None, "structural": 0.0},
}

ALASAN_STUB = "data historis belum cukup panjang untuk ticker ini (stub)"

DISPLAY = {
    "volume_anomaly": ("vas.zscore", "Z-score volume vs baseline 90 hari",
                       "fetch-daily-transaction"),
    "broker_concentration": ("bci.top3_share", "Pangsa net buy 3 broker teratas",
                             "fetch-broker-summary-top"),
    "price_fundamental": ("pfd.return_90d", "Return 90 hari bursa", "fetch-close"),
    "free_float": ("ffs.pct", "Free float", "fetch-free-float"),
    "foreign_flow": ("frd.foreign_net_30d", "Arus asing bersih 30 hari bursa",
                     "fetch-foreign-flow"),
    "structural": ("sss.insider_sells", "Transaksi jual insider 90 hari", "fetch-filings"),
}


def _deterministic_score(symbol: str, probe: str) -> float:
    """Skor stabil untuk ticker di luar profil bawaan.

    Diturunkan dari hash, bukan random: tes agen yang berubah hasil tiap
    dijalankan tidak membuktikan apa pun.
    """
    digest = sha256(f"{symbol}:{probe}".encode()).digest()
    return round(digest[0] / 255 * 100, 1)


class StubProbe:
    """Pengganti sementara satu probe. Memenuhi Protocol Probe apa adanya."""

    def __init__(self, name: ProbeName) -> None:
        self.name: ProbeName = name
        self._real = PROBES[name]
        self.component = self._real.component

    def cost_estimate(self, symbol: str) -> int:
        """Ikut probe asli — perencana harus berlatih dengan anggaran sungguhan."""
        return self._real.cost_estimate(symbol)

    def run(self, symbol: str, ctx: Context | None = None) -> ProbeResult:
        profil = PROFILES.get(symbol)
        skor = profil[self.name] if profil and self.name in profil \
            else _deterministic_score(symbol, self.name)

        if skor is None:
            return ProbeResult(probe=self.name, sub_score=None,
                               unavailable_reason=ALASAN_STUB, credits_spent=0)

        ev_id, label, endpoint = DISPLAY[self.name]
        as_of = getattr(ctx, "as_of", None) or STUB_AS_OF
        return ProbeResult(
            probe=self.name, sub_score=skor, credits_spent=0,
            evidence=[EvidenceEntry(
                id=ev_id, label=label, value=skor, display=f"{skor:.0f} (stub)",
                probe=self.name, source_endpoint=endpoint,
                source_params={"symbol": symbol, "stub": True},
                source_transport="rest", as_of=stamp(as_of), credits_spent=0,
            )],
        )


STUB_PROBES: dict[str, StubProbe] = {name: StubProbe(name) for name in PROBES}


def describe() -> str:
    lines = ["probe stub — nol kredit, nol jaringan, hasil deterministik", ""]
    for symbol in (*PROFILES, "BBRI"):
        hasil = []
        for probe in STUB_PROBES.values():
            r = probe.run(symbol)
            hasil.append(f"{probe.component}={r.sub_score if r.sub_score is not None else 'n/a'}")
        lines.append(f"  {symbol}  " + "  ".join(hasil))
    return "\n".join(lines)


if __name__ == "__main__":
    from core.console import setup_console

    setup_console()
    print(describe())
