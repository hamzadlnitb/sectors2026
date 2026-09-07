"""Bangkitkan fixture transkrip investigasi.

Fixture ditulis lewat model pydantic supaya mustahil menyimpang dari kontrak.
Ticker sengaja fiktif (FIXA/FIXB/FIXC) — fixture tidak boleh menyiratkan klaim
apa pun tentang emiten sungguhan.

    python3 fixtures/generate.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts.schemas import (  # noqa: E402
    ComponentScore, DISCLAIMER, EvidenceEntry, Hypothesis,
    InvestigationTranscript, Plan, Step, band_for_score,
)

OUT = Path(__file__).resolve().parent / "transcripts"
WIB = timezone(timedelta(hours=7))
AS_OF = date(2026, 9, 5)
STAMP = datetime(2026, 9, 5, 17, 30, tzinfo=WIB)

WEIGHTS = {"BCI": 0.24, "VAS": 0.18, "PFD": 0.16, "FFS": 0.12, "FRD": 0.18, "SSS": 0.12}
BASELINE = 23  # biaya kalau keenam probe dijalankan
WEIGHTS_VERSION = "cal-fixture"  # diganti versi kalibrasi asli setelah H1 selesai


def ev(id_, label, value, display, probe, endpoint, params, transport, credits) -> EvidenceEntry:
    return EvidenceEntry(
        id=id_, label=label, value=value, display=display, probe=probe,
        source_endpoint=endpoint, source_params=params, source_transport=transport,
        as_of=STAMP, credits_spent=credits,
    )


def components(scores: dict[str, float | None], evidence_map: dict[str, list[str]]):
    return [
        ComponentScore(
            code=code, weight=weight,
            sub_score=scores.get(code),
            evidence_ids=evidence_map.get(code, []),
            investigated=code in scores,
        )
        for code, weight in WEIGHTS.items()
    ]


def composite(scores: dict[str, float]) -> tuple[int, float]:
    total_w = sum(WEIGHTS[c] for c in scores)
    score = sum(WEIGHTS[c] * s for c, s in scores.items()) / total_w
    return round(score), round(total_w, 2)


# ── FIXA — normal: agen berhenti setelah 2 langkah ───────────────────────────
def fix_a() -> InvestigationTranscript:
    evidence = [
        ev("vas.zscore", "Z-score volume vs baseline 90 hari", 0.4, "0,4σ",
           "volume_anomaly", "fetch-daily-transaction",
           {"symbol": "FIXA", "start": "2026-06-08", "end": "2026-09-05"}, "rest", 2),
        ev("vas.volume_ratio", "Volume hari ini vs rata-rata", 1.1, "1,1×",
           "volume_anomaly", "fetch-daily-transaction",
           {"symbol": "FIXA", "start": "2026-06-08", "end": "2026-09-05"}, "rest", 0),
        ev("ffs.pct", "Free float", 0.62, "62%",
           "free_float", "fetch-free-float", {"sub_sector": "banks"}, "mcp", 2),
    ]
    scores = {"VAS": 20.0, "FFS": 15.0}
    score, conf = composite(scores)
    return InvestigationTranscript(
        symbol="FIXA", as_of=AS_OF, weights_version=WEIGHTS_VERSION,
        plan=Plan(
            hypotheses=[
                Hypothesis(id="h1", claim="Volume bergerak tidak wajar",
                           probes=["volume_anomaly"], priority=1),
                Hypothesis(id="h2", claim="Saham beredar terlalu sedikit sehingga mudah digerakkan",
                           probes=["free_float"], priority=2),
            ],
            credit_budget_requested=8,
            rationale="Sinyal Tier-1 tenang: volume mendekati rata-rata, kapitalisasi besar. "
                      "Mulai dari dua probe termurah dan berhenti kalau keduanya bersih.",
        ),
        steps=[
            Step(step=1, hypothesis="h1", probe="volume_anomaly", finding="refuted",
                 next_action="continue",
                 reason="Volume hanya 0,4σ di atas baseline. Hipotesis pergerakan tidak wajar terbantah.",
                 credits_spent=2, credits_remaining=6),
            Step(step=2, hypothesis="h2", probe="free_float", finding="refuted",
                 next_action="conclude",
                 reason="Free float 62% terlalu longgar untuk digerakkan segelintir pihak. "
                        "Dua hipotesis terbantah; melanjutkan ke probe mahal tidak sepadan.",
                 credits_spent=2, credits_remaining=4),
        ],
        evidence=evidence,
        components=components(scores, {"VAS": ["vas.zscore", "vas.volume_ratio"], "FFS": ["ffs.pct"]}),
        pantau_score=score, band=band_for_score(score), confidence=conf,
        credits_total=4, baseline_credits=BASELINE,
        narrative="Tidak ada pola tidak biasa terdeteksi. Volume perdagangan hanya 0,4σ di atas "
                  "baseline 90 hari, dan free float 62% membuat saham ini sulit digerakkan oleh "
                  "segelintir pihak. Penyelidikan dihentikan setelah dua langkah karena kedua "
                  "hipotesis awal terbantah.",
        narrative_source="llm", disclaimer=DISCLAIMER,
    )


# ── FIXB — waspada: investigasi lima langkah ─────────────────────────────────
def fix_b() -> InvestigationTranscript:
    evidence = [
        ev("bci.top3_share", "Pangsa net buy 3 broker teratas", 0.78, "78%",
           "broker_concentration", "fetch-broker-summary-top",
           {"symbol": "FIXB", "start": "2026-08-22", "end": "2026-09-05"}, "rest", 4),
        ev("bci.hhi", "Indeks Herfindahl konsentrasi broker", 0.31, "0,31",
           "broker_concentration", "fetch-broker-summary",
           {"symbol": "FIXB", "start": "2026-08-22", "end": "2026-09-05"}, "rest", 2),
        ev("vas.zscore", "Z-score volume vs baseline 90 hari", 4.1, "4,1σ",
           "volume_anomaly", "fetch-daily-transaction",
           {"symbol": "FIXB", "start": "2026-06-08", "end": "2026-09-05"}, "rest", 2),
        ev("pfd.return_90d", "Return 90 hari", 1.42, "+142%",
           "price_fundamental", "fetch-close", {"date": "2026-09-05"}, "rest", 2),
        ev("pfd.earnings_change", "Perubahan laba bersih year-on-year", -0.08, "-8%",
           "price_fundamental", "fetch-quarterly-financials",
           {"symbol": "FIXB", "n_quarters": 8}, "mcp", 2),
        ev("frd.foreign_net_30d", "Arus asing bersih 30 hari", -184_000_000_000, "-Rp 184 M",
           "foreign_flow", "fetch-foreign-flow",
           {"symbol": "FIXB", "start": "2026-08-06", "end": "2026-09-05"}, "rest", 4),
        ev("sss.insider_sells", "Transaksi jual insider 90 hari", 3, "3 transaksi",
           "structural", "fetch-filings",
           {"symbol": "FIXB", "transaction_type": "sell", "start": "2026-06-08"}, "mcp", 5),
    ]
    scores = {"BCI": 88.0, "VAS": 76.0, "PFD": 71.0, "FRD": 68.0, "SSS": 55.0}
    score, conf = composite(scores)
    return InvestigationTranscript(
        symbol="FIXB", as_of=AS_OF, weights_version=WEIGHTS_VERSION,
        plan=Plan(
            hypotheses=[
                Hypothesis(id="h1", claim="Volume tidak wajar tanpa dukungan fundamental",
                           probes=["volume_anomaly", "price_fundamental"], priority=1),
                Hypothesis(id="h2", claim="Perdagangan terkonsentrasi di sedikit broker",
                           probes=["broker_concentration"], priority=2),
                Hypothesis(id="h3", claim="Asing mendistribusikan ke ritel saat harga naik",
                           probes=["foreign_flow", "structural"], priority=3),
            ],
            credit_budget_requested=21,
            rationale="Sinyal Tier-1 keras: volume 4σ, harga naik tajam 90 hari. "
                      "Dahulukan probe broker karena paling menentukan meski paling mahal.",
        ),
        steps=[
            Step(step=1, hypothesis="h2", probe="broker_concentration", finding="confirmed",
                 next_action="continue",
                 reason="78% net buy dikuasai tiga broker. Konsentrasi ekstrem, lanjutkan.",
                 credits_spent=6, credits_remaining=15),
            Step(step=2, hypothesis="h1", probe="volume_anomaly", finding="confirmed",
                 next_action="continue", reason="Volume 4,1σ di atas baseline.",
                 credits_spent=2, credits_remaining=13),
            Step(step=3, hypothesis="h1", probe="price_fundamental", finding="confirmed",
                 next_action="continue",
                 reason="Harga +142% sementara laba bersih turun 8%. Divergensi lebar.",
                 credits_spent=4, credits_remaining=9),
            Step(step=4, hypothesis="h3", probe="foreign_flow", finding="confirmed",
                 next_action="continue",
                 reason="Asing keluar bersih Rp 184 M saat harga naik. Pola distribusi.",
                 credits_spent=4, credits_remaining=5),
            Step(step=5, hypothesis="h3", probe="structural", finding="confirmed",
                 next_action="conclude",
                 reason="Tiga transaksi jual insider dalam 90 hari menguatkan h3. "
                        "Bukti sudah cukup; free float tidak akan mengubah band.",
                 credits_spent=5, credits_remaining=0),
        ],
        evidence=evidence,
        components=components(scores, {
            "BCI": ["bci.top3_share", "bci.hhi"], "VAS": ["vas.zscore"],
            "PFD": ["pfd.return_90d", "pfd.earnings_change"],
            "FRD": ["frd.foreign_net_30d"], "SSS": ["sss.insider_sells"],
        }),
        pantau_score=score, band=band_for_score(score), confidence=conf,
        credits_total=21, baseline_credits=BASELINE,
        narrative="Beberapa indikator menunjukkan pola tidak biasa. Sebanyak 78% net buy dikuasai "
                  "tiga broker, volume berada 4,1σ di atas baseline, dan harga naik 142% dalam 90 "
                  "hari sementara laba bersih justru turun 8%. Pada periode yang sama asing keluar "
                  "bersih Rp 184 M dan tercatat 3 transaksi jual insider.",
        narrative_source="llm", disclaimer=DISCLAIMER,
    )


# ── FIXC — eskalasi: agen membuka probe di luar rencana ──────────────────────
def fix_c() -> InvestigationTranscript:
    evidence = [
        ev("vas.zscore", "Z-score volume vs baseline 90 hari", 6.2, "6,2σ",
           "volume_anomaly", "fetch-daily-transaction",
           {"symbol": "FIXC", "start": "2026-06-08", "end": "2026-09-05"}, "rest", 2),
        ev("ffs.pct", "Free float", 0.04, "4%",
           "free_float", "fetch-free-float", {"sub_sector": "properties-real-estate"}, "mcp", 2),
        ev("sss.rights_issues", "Rights issue 24 bulan terakhir", 2, "2 kali",
           "structural", "fetch-corporate-actions", {"symbol": "FIXC"}, "mcp", 3),
        ev("sss.prior_suspension", "Suspensi sebelumnya", "2025-11-14", "14 November 2025",
           "structural", "fetch-suspensions",
           {"symbol": "FIXC", "start": "2024-09-05", "end": "2026-09-05"}, "rest", 2),
        ev("frd.foreign_net_30d", "Arus asing bersih 30 hari", -47_000_000_000, "-Rp 47 M",
           "foreign_flow", "fetch-foreign-flow",
           {"symbol": "FIXC", "start": "2026-08-06", "end": "2026-09-05"}, "rest", 4),
    ]
    scores = {"VAS": 92.0, "FFS": 95.0, "SSS": 78.0, "FRD": 84.0}
    score, conf = composite(scores)
    return InvestigationTranscript(
        symbol="FIXC", as_of=AS_OF, weights_version=WEIGHTS_VERSION,
        plan=Plan(
            hypotheses=[
                Hypothesis(id="h1", claim="Volume meledak pada saham berkapitalisasi kecil",
                           probes=["volume_anomaly"], priority=1),
                Hypothesis(id="h2", claim="Saham beredar terlalu sedikit sehingga mudah digerakkan",
                           probes=["free_float"], priority=2),
                Hypothesis(id="h3", claim="Asing mendistribusikan ke ritel",
                           probes=["foreign_flow"], priority=3),
            ],
            credit_budget_requested=8,
            rationale="Kapitalisasi kecil dengan volume 6σ. Mulai dari dua probe murah; "
                      "pagu ditahan dulu karena investigasi 12 hari lalu berakhir normal.",
        ),
        steps=[
            Step(step=1, hypothesis="h1", probe="volume_anomaly", finding="confirmed",
                 next_action="continue", reason="Volume 6,2σ di atas baseline. Ekstrem.",
                 credits_spent=2, credits_remaining=6),
            Step(step=2, hypothesis="h2", probe="free_float", finding="confirmed",
                 next_action="escalate", new_probe="structural", budget_granted=7,
                 reason="Free float hanya 4% — jauh lebih ketat dari perkiraan awal. Kombinasi "
                        "float 4% dan volume 6σ menuntut pemeriksaan corporate action, yang tidak "
                        "ada di rencana awal. Meminta tambahan pagu 7 kredit; dikabulkan.",
                 credits_spent=2, credits_remaining=11),
            Step(step=3, hypothesis="h2", probe="structural", finding="confirmed",
                 next_action="continue",
                 reason="Dua kali rights issue dalam 24 bulan, dan pernah disuspend 14 November 2025. "
                        "Eskalasi terbayar: temuan ini menaikkan band.",
                 credits_spent=5, credits_remaining=6),
            Step(step=4, hypothesis="h3", probe="foreign_flow", finding="confirmed",
                 next_action="conclude",
                 reason="Asing keluar bersih Rp 47 M. Bukti cukup; probe broker dilewati karena "
                        "band sudah tidak akan berubah dan biayanya paling mahal.",
                 credits_spent=4, credits_remaining=2),
        ],
        evidence=evidence,
        components=components(scores, {
            "VAS": ["vas.zscore"], "FFS": ["ffs.pct"],
            "SSS": ["sss.rights_issues", "sss.prior_suspension"],
            "FRD": ["frd.foreign_net_30d"],
        }),
        pantau_score=score, band=band_for_score(score), confidence=conf,
        credits_total=13, baseline_credits=BASELINE,
        narrative="Banyak indikator menunjukkan pola tidak biasa secara bersamaan. Free float hanya "
                  "4% sementara volume berada 6,2σ di atas baseline. Emiten ini menggelar rights "
                  "issue 2 kali dalam 24 bulan terakhir dan pernah disuspend pada 14 November 2025. "
                  "Dalam 30 hari terakhir asing keluar bersih Rp 47 M.",
        narrative_source="llm", memory_ref="FIXC-2026-08-24", disclaimer=DISCLAIMER,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, builder in (("normal", fix_a), ("waspada", fix_b), ("eskalasi", fix_c)):
        t = builder()
        (OUT / f"{name}.json").write_text(t.model_dump_json(indent=2) + "\n")
        print(f"{name}.json  {t.symbol}  skor {t.pantau_score} ({t.band})  "
              f"{t.credits_total}/{t.baseline_credits} kredit  keyakinan {t.confidence}")


if __name__ == "__main__":
    main()
