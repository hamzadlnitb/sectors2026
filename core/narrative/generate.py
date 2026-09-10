"""Menulis narasi putusan, lalu memaksanya lolos dua penjaga. [AD-4][K5]

Urutannya sengaja: LLM menulis, kode memutuskan boleh atau tidak. Kalau
keluarannya memuat angka yang tidak ada di buku bukti, memuat bahasa saran
finansial, atau LLM-nya mati sama sekali, yang keluar template deterministik
yang dirakit dari buku bukti yang sama. `narrate()` tidak pernah melempar dan
tidak pernah mengembalikan teks yang belum lolos validator — pemanggil cukup
menyimpan hasilnya beserta labelnya ke `InvestigationTranscript`.

Dua penjaga, dua alasan berbeda:

* **Validator sitasi** (`core.narrative.validate`) — kredibilitas. Angka karangan
  meruntuhkan seluruh klaim produk.
* **Larangan kosakata** (`tools.vocab_guard`) — kepatuhan. Bahasa saran finansial
  bukan pengurangan nilai, tapi diskualifikasi, jadi diperiksa di jalur panas
  juga, bukan cuma di CI. Template sendiri ikut diperiksa tesnya.
"""

from __future__ import annotations

from typing import Any, Literal

from core.llm import LLMError
from core.narrative.validate import unsupported_numbers, unsupported_tickers
from tools.vocab_guard import periksa_teks

PROMPT_VERSION = "narrative-v1"

SYSTEM = (
    "Kamu menulis ringkasan temuan untuk PANTAU, alat pemantau pola tidak biasa "
    "saham IDX. Tulis 3-4 kalimat Bahasa Indonesia yang padat dan datar.\n"
    "Aturan keras:\n"
    "1. Setiap angka yang kamu tulis WAJIB disalin persis dari buku bukti yang "
    "diberikan. Dilarang menghitung, membulatkan, atau menambahkan angka baru.\n"
    "2. Deskripsikan pola, jangan menyuruh orang bertransaksi. Dilarang menyebut "
    "target harga, ajakan bertransaksi, atau penilaian layak-tidaknya sebuah saham.\n"  # vocab-ok: prompt melarang frasa ini, bukan memakainya
    "3. Jangan menyebut skor, band, atau tingkat keyakinan sebagai angka.\n"
    "4. Balas hanya narasinya, tanpa judul dan tanpa daftar berpoin."
)

_BAND_PEMBUKA = {
    "normal": "Tidak ada pola tidak biasa yang menonjol pada {s}.",
    "perhatian": "Beberapa indikator pada {s} berada di luar kebiasaan.",
    "waspada": "Beberapa indikator pada {s} menunjukkan pola tidak biasa.",
    "sangat_waspada": (
        "Banyak indikator pada {s} menunjukkan pola tidak biasa secara bersamaan."
    ),
}

# Bilangan sebagai kata, bukan angka: kata bukan sitasi, jadi tidak menuntut
# padanan di buku bukti. Ini yang membuat template bisa menyebut jumlah langkah
# tanpa melanggar validatornya sendiri. [AD-4]
_KATA_BILANGAN = (
    "nol", "satu", "dua", "tiga", "empat", "lima", "enam",
    "tujuh", "delapan", "sembilan", "sepuluh",
)


def _kata_bilangan(n: int) -> str:
    return _KATA_BILANGAN[n] if 0 <= n < len(_KATA_BILANGAN) else "beberapa"


def _buku_bukti(evidence: list[Any]) -> str:
    return "\n".join(
        f"- {getattr(e, 'label', '')}: {getattr(e, 'display', '')}" for e in evidence
    )


def _prompt(symbol: str, composite: Any, evidence: list[Any], steps: list[Any]) -> str:
    temuan = "\n".join(
        f"- {getattr(s, 'probe', '')}: {getattr(s, 'finding', '')} — {getattr(s, 'reason', '')}"
        for s in steps
    )
    return (
        f"Ticker: {symbol}\n"
        f"Band putusan: {getattr(composite, 'band', 'normal')}\n\n"
        f"Buku bukti (SATU-SATUNYA sumber angka yang boleh kamu pakai):\n"
        f"{_buku_bukti(evidence) or '- (kosong)'}\n\n"
        f"Langkah penyelidikan:\n{temuan or '- (tidak ada)'}\n\n"
        f"Tulis 3-4 kalimat yang merangkum apa yang ditemukan."
    )


def template(symbol: str, composite: Any, evidence: list[Any], steps: list[Any]) -> str:
    """Rakitan deterministik dari buku bukti. Jalur ini tidak pernah gagal.

    Dibuka sebagai fungsi publik supaya tes bisa memeriksanya langsung: template
    yang sendirinya melanggar validator atau larangan kosakata akan menjadikan
    fallback-nya percuma.
    """
    band = str(getattr(composite, "band", "normal"))
    kalimat = [_BAND_PEMBUKA.get(band, _BAND_PEMBUKA["perhatian"]).format(s=symbol)]

    dikutip = [
        f"{getattr(e, 'label', '')} {getattr(e, 'display', '')}".strip()
        for e in evidence[:4]
        if getattr(e, "display", None)
    ]
    if dikutip:
        kalimat.append("Bukti yang terkumpul: " + "; ".join(dikutip) + ".")

    diselidiki = {getattr(s, "probe", None) for s in steps if getattr(s, "probe", None)}
    if steps:
        kalimat.append(
            f"Putusan disusun dari {_kata_bilangan(len(steps))} langkah penyelidikan "
            f"yang menyentuh {_kata_bilangan(len(diselidiki))} probe."
        )
    kalimat.append(
        "Seluruh angka di atas berasal dari buku bukti investigasi ini dan bisa "
        "ditelusuri ke sumber datanya."
    )
    return " ".join(kalimat)


def narrate(*, symbol: str, composite: Any, evidence: list[Any],
            steps: list[Any], llm: Any) -> tuple[str, Literal["llm", "template"]]:
    """Narasi putusan + asal-usulnya.

    ('...', 'llm') kalau keluaran LLM lolos validator sitasi dan larangan
    kosakata. ('...', 'template') untuk semua keadaan lain: angka karangan,
    bahasa saran finansial, keluaran kosong, LLM melempar `LLMError`/`JSONInvalid`,
    atau klien LLM rusak sama sekali. Label itu ikut disimpan ke transkrip supaya
    UI bisa jujur soal dari mana kalimatnya datang.
    """
    teks = ""
    try:
        teks = (llm.ask_text(
            system=SYSTEM,
            prompt=_prompt(symbol, composite, evidence, steps),
            prompt_version=PROMPT_VERSION,
            max_tokens=600,
        ) or "").strip()
    except LLMError:
        # Sudah bentuk yang kita janjikan ditangani di sini, bukan dinaikkan. [AD-6]
        teks = ""
    except Exception:  # noqa: BLE001 — klien pihak ketiga bebas melempar apa saja;
        # narasi bukan alasan sah untuk menjatuhkan investigasi yang sudah dibayar.
        teks = ""

    if (teks and not unsupported_numbers(teks, evidence)
            and not unsupported_tickers(teks, symbol)
            and not periksa_teks(teks)):
        return teks, "llm"
    return template(symbol, composite, evidence, steps), "template"
