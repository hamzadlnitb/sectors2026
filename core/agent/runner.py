"""Merangkai tiga tahap jadi satu investigasi utuh.

    python3 -m core.agent BBCA              # LLM sungguhan kalau kunci ada
    python3 -m core.agent BBCA --offline    # FakeLLM, nol jaringan

Mode offline bukan sekadar kenyamanan tes: `make demo` harus jalan di mesin
juri tanpa kunci apa pun. [AD-1][AD-2]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.schemas import InvestigationTranscript  # noqa: E402
from core.agent import planner as planner_mod  # noqa: E402
from core.agent.adjudicator import adjudicate  # noqa: E402
from core.agent.budget import Budget, max_credits  # noqa: E402
from core.agent.guardrails import Guardrails  # noqa: E402
from core.agent.investigator import investigate  # noqa: E402
from core.agent.memory import Memory  # noqa: E402
from core.agent.transcript import save  # noqa: E402
from core.ingest.warehouse import Warehouse  # noqa: E402
from core.probes.base import Context  # noqa: E402
from core.sectors.redact import get_logger  # noqa: E402

log = get_logger(__name__)


def tier1_signals(symbol: str, ctx: Context) -> dict:
    """Sinyal murah dari warehouse untuk menyalakan perencana. Nol kredit.

    Sengaja kasar: ini bukan analisis, ini alasan supaya perencana punya dasar
    memilih probe mana yang layak dibeli. Analisis sesungguhnya ada di probe.
    """
    sinyal: dict[str, str] = {}
    try:
        harga = ctx.price_history(symbol)
        if not harga.empty:
            sinyal["hari_bursa_tersedia"] = str(len(harga))
            if "volume" in harga.columns and len(harga) >= 20:
                v = harga["volume"].astype(float)
                dasar = v.iloc[:-1].median()
                if dasar > 0:
                    sinyal["volume_terakhir_vs_median"] = f"{v.iloc[-1] / dasar:.1f}x"
            if "close_price" in harga.columns and len(harga) >= 2:
                c = harga["close_price"].astype(float)
                if c.iloc[0] > 0:
                    sinyal["perubahan_harga_periode"] = f"{(c.iloc[-1] / c.iloc[0] - 1) * 100:+.0f}%"
        profil = ctx.symbol_frame("company_profile", symbol)
        if not profil.empty:
            row = profil.iloc[0]
            if "sub_sector" in profil.columns:
                sinyal["subsektor"] = str(row["sub_sector"])
            if "market_cap" in profil.columns and row["market_cap"]:
                sinyal["kapitalisasi_rp"] = f"{float(row['market_cap']):.3g}"
    except Exception as exc:  # noqa: BLE001 — sinyal kosong lebih baik daripada
        # investigasi yang batal sebelum mulai. Perencana punya fallback.
        log.warning("sinyal Tier-1 %s gagal dihitung: %s", symbol, exc)
    return sinyal


def _offline_llm():
    """FakeLLM yang cukup untuk satu investigasi penuh tanpa jaringan.

    Sengaja TIDAK memberi jawaban apa pun: setiap permintaan gagal, sehingga
    perencana dan penyelidik jatuh ke jalur cadangan deterministik. Yang
    ditunjukkan mode ini bukan kecerdasan agen, melainkan bahwa sistem tetap
    menghasilkan transkrip sah ketika LLM tidak tersedia sama sekali. [AD-6]
    """
    from core.llm import FakeLLM

    return FakeLLM()


def investigate_symbol(symbol: str, *, as_of: date | None = None,
                       offline: bool = False, llm=None,
                       warehouse: Warehouse | None = None,
                       memory: Memory | None = None,
                       client=None, persist: bool = True) -> InvestigationTranscript:
    symbol = symbol.strip().upper().removesuffix(".JK")
    hari = as_of or date.today()

    wh = warehouse or Warehouse()
    ctx = Context(as_of=hari, warehouse=wh, client=client, phase="agent")

    if llm is None:
        if offline:
            llm = _offline_llm()
        else:
            from core.llm import LLM
            llm = LLM.from_env()

    mem = memory if memory is not None else Memory()
    riwayat = mem.recall(symbol, before=hari)

    sinyal = tier1_signals(symbol, ctx)
    rencana, dari_llm = planner_mod.plan(
        symbol=symbol, as_of=hari, signals=sinyal, ceiling=max_credits(),
        llm=llm, memory=riwayat,
    )
    log.info("rencana %s (%s): minta %d kredit, %d hipotesis",
             symbol, "LLM" if dari_llm else "cadangan",
             rencana.credit_budget_requested, len(rencana.hypotheses))

    budget = Budget.for_plan(rencana.credit_budget_requested)
    inv = investigate(symbol=symbol, plan=rencana, ctx=ctx, budget=budget,
                      llm=llm, guards=Guardrails())

    transkrip = adjudicate(symbol=symbol, as_of=hari, plan=rencana, inv=inv,
                           llm=llm, memory=riwayat)

    if persist:
        path = save(transkrip)
        mem.remember(transkrip, path)
        log.info("transkrip %s disimpan di %s", symbol, path)
    return transkrip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Investigasi risiko satu emiten IDX.")
    ap.add_argument("symbol")
    ap.add_argument("--as-of", type=date.fromisoformat, default=None)
    ap.add_argument("--offline", action="store_true",
                    help="Pakai FakeLLM — nol jaringan, nol kunci API")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)

    t = investigate_symbol(args.symbol, as_of=args.as_of, offline=args.offline,
                           persist=not args.no_save)

    hemat = 100 * (1 - t.credits_total / t.baseline_credits) if t.baseline_credits else 0
    print(f"\n{t.symbol} — {t.as_of}")
    print(f"  skor        {t.pantau_score} ({t.band})")
    print(f"  keyakinan   {t.confidence:.0%}  ({len(t.plan.hypotheses)} hipotesis, "
          f"{len(t.steps)} langkah)")
    print(f"  kredit      {t.credits_total} vs {t.baseline_credits} menyeluruh "
          f"({hemat:.0f}% lebih hemat)")
    print(f"  narasi      [{t.narrative_source}] {t.narrative[:110]}")
    for s in t.steps:
        ek = f"  +{s.budget_granted}" if s.budget_granted else ""
        print(f"   {s.step}. {s.probe:22s} {s.finding:13s} → {s.next_action}{ek}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
