"""Larangan kosakata: nol bahasa saran finansial di seluruh keluaran. [K5]

Rules lomba melarang saran investasi, dan pelanggarannya fatal — bukan
pengurangan nilai, tapi diskualifikasi. Karena narasi ditulis LLM, larangan ini
tidak bisa dititipkan ke prompt: prompt bisa diabaikan, CI tidak.

**Kenapa bukan grep polos.** `grep -i jual` akan menolak kalimat
"tercatat 3 transaksi jual insider" — deskripsi faktual tentang transaksi orang
lain, bukan ajakan menjual. Kalimat itu ada di `fixtures/transcripts/waspada.json`
yang sudah beku. Penjaga yang menolaknya akan dimatikan orang dalam seminggu,
dan setelah itu tidak menjaga apa pun.

Jadi dua tingkat:

1. **Frasa terlarang mutlak** — "target harga", "rekomendasi", "cuan",
   "pasti naik", "layak beli". Tidak ada konteks yang menyelamatkannya.
2. **Kata peka konteks** — "beli" dan "jual" berdiri sendiri dilarang, tapi
   diizinkan dalam kolokasi faktual: "net buy", "aksi jual", "transaksi jual
   insider", "tekanan beli", "jual bersih".

Kata Inggris `buy`/`sell` sengaja TIDAK dilarang: keduanya nama kolom data
(`buy_value`, `net_value`) dan muncul di label bukti seperti "Pangsa net buy 3
broker teratas". Melarangnya berarti melarang menyebut datanya sendiri.

    make vocab
    python tools/vocab_guard.py --paths runs fixtures/transcripts
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.console import setup_console  # noqa: E402

# Disclaimer resmi memuat "saran investasi" dan memang harus. Dikecualikan
# sebagai teks utuh, bukan sebagai kata — supaya "ini saran investasi yang bagus"
# tetap tertangkap.
DISCLAIMER = "PANTAU adalah alat informasi dan analisis, bukan saran investasi."

TERLARANG: tuple[tuple[str, str], ...] = (
    (r"target\s+harga", "menyebut target harga = saran finansial"),
    (r"harga\s+target", "menyebut target harga = saran finansial"),
    (r"rekomendasi", "kata 'rekomendasi' dilarang tanpa kecuali"),
    (r"\bcuan\b", "bahasa promosi keuntungan"),
    (r"pasti\s+(naik|untung|cuan)", "menjanjikan hasil"),
    (r"dijamin\s+(naik|untung|cuan)", "menjanjikan hasil"),
    (r"(wajib|layak|saatnya|buruan|segera|jangan)\s+(beli|jual)", "ajakan bertransaksi"),
    (r"\b(beli|jual)lah\b", "kalimat perintah bertransaksi"),
    (r"\bportofolio\s+anda\b", "menasihati portofolio pembaca"),
    (r"saran\s+investasi", "menyebut diri sebagai saran investasi"),
)

PEKA = re.compile(r"\b(beli|jual)\b", re.IGNORECASE)

# Kata di sekitar yang membuat "beli"/"jual" jadi deskripsi, bukan ajakan.
SEBELUM = {
    "net", "aksi", "transaksi", "tekanan", "volume", "nilai", "harga", "porsi",
    "pangsa", "total", "sisi", "arus", "pihak", "rasio", "jumlah", "aktivitas",
}
SESUDAH = {"insider", "bersih", "asing", "ritel", "domestik"}

# Berkas yang isinya memang teks keluaran ke pengguna.
TARGET_JSON = (
    "fixtures/transcripts",
    "runs",
    "web/public/data",
    "reports",
)
TARGET_PY = ("core", "tools", "evals")

LEWATI_DIR = {"__pycache__", ".git", "node_modules", ".venv", "cache"}


@dataclass
class Pelanggaran:
    file: str
    lokasi: str
    kutipan: str
    alasan: str

    def __str__(self) -> str:
        return f"  {self.file}:{self.lokasi}\n      \"{self.kutipan}\"\n      -> {self.alasan}"


def _tanpa_disclaimer(teks: str) -> str:
    return teks.replace(DISCLAIMER, " ")


def periksa_teks(teks: str) -> list[tuple[str, str]]:
    """Kembalikan (kutipan, alasan) untuk tiap pelanggaran dalam satu string."""
    bersih = _tanpa_disclaimer(teks)
    keluar: list[tuple[str, str]] = []

    for pola, alasan in TERLARANG:
        for m in re.finditer(pola, bersih, re.IGNORECASE):
            keluar.append((_kutip(bersih, m.start(), m.end()), alasan))

    for m in PEKA.finditer(bersih):
        if _berkolokasi(bersih, m):
            continue
        keluar.append((
            _kutip(bersih, m.start(), m.end()),
            f"kata '{m.group(1)}' berdiri sendiri — pakai kolokasi faktual "
            f"(mis. 'transaksi jual insider', 'net beli') atau tulis ulang",
        ))
    return keluar


def _berkolokasi(teks: str, m: re.Match) -> bool:
    sebelum = re.findall(r"[\w-]+", teks[max(0, m.start() - 24):m.start()])
    sesudah = re.findall(r"[\w-]+", teks[m.end():m.end() + 24])
    if sebelum and sebelum[-1].lower() in SEBELUM:
        return True
    return bool(sesudah and sesudah[0].lower() in SESUDAH)


def _kutip(teks: str, mulai: int, akhir: int, lebar: int = 38) -> str:
    kiri = max(0, mulai - lebar)
    kanan = min(len(teks), akhir + lebar)
    potongan = teks[kiri:kanan].replace("\n", " ").strip()
    return ("…" if kiri else "") + potongan + ("…" if kanan < len(teks) else "")


# ── JSON ────────────────────────────────────────────────────────────────────
def periksa_json(path: Path) -> list[Pelanggaran]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [Pelanggaran(str(path), "-", "", f"tidak bisa dibaca: {exc}")]

    keluar: list[Pelanggaran] = []
    for jalur, teks in _strings(data):
        for kutipan, alasan in periksa_teks(teks):
            keluar.append(Pelanggaran(str(path), jalur, kutipan, alasan))
    return keluar


def _strings(node, jalur: str = "$"):
    if isinstance(node, str):
        yield jalur, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, f"{jalur}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _strings(v, f"{jalur}[{i}]")


# ── Python ──────────────────────────────────────────────────────────────────
OPT_OUT = re.compile(r"#\s*vocab-ok:\s*\S")
"""Penanda pengecualian per baris, WAJIB disertai alasan setelah titik dua.

Ada karena sebagian literal memang harus memuat kata terlarang untuk
mencocokkannya — pola regex penyaring jenis transaksi, misalnya. Bentuknya
sengaja terlihat di diff dan menuntut alasan tertulis, bukan daftar
pengecualian tersembunyi di berkas konfigurasi yang tidak pernah dibaca lagi.
"""


def periksa_python(path: Path) -> list[Pelanggaran]:
    """Hanya literal string yang diperiksa.

    Bukan seluruh berkas: nama variabel dan komentar bukan keluaran ke pengguna,
    dan berkas ini sendiri penuh kata terlarang karena memang mendaftarkannya.
    """
    try:
        sumber = path.read_text(encoding="utf-8")
        pohon = ast.parse(sumber, filename=str(path))
    except (SyntaxError, OSError) as exc:
        return [Pelanggaran(str(path), "-", "", f"tidak bisa diurai: {exc}")]

    baris = sumber.splitlines()
    keluar: list[Pelanggaran] = []
    for node in ast.walk(pohon):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if _dikecualikan(baris, node):
            continue
        for kutipan, alasan in periksa_teks(node.value):
            keluar.append(Pelanggaran(str(path), str(node.lineno), kutipan, alasan))
    return keluar


def _dikecualikan(baris: list[str], node: ast.Constant) -> bool:
    """Penanda boleh di baris literalnya, atau di baris tepat di atasnya.

    Yang di atas dipakai untuk literal panjang: menempelkan komentar di ujung
    string multi-baris membuatnya tidak terbaca.
    """
    akhir = node.end_lineno or node.lineno
    for nomor in range(node.lineno - 1, akhir + 1):
        if 0 < nomor <= len(baris) and OPT_OUT.search(baris[nomor - 1]):
            return True
    return False


def kumpulkan(paths: list[Path]) -> list[Path]:
    keluar: list[Path] = []
    for base in paths:
        if base.is_file():
            keluar.append(base)
            continue
        for path in base.rglob("*"):
            if any(bagian in LEWATI_DIR for bagian in path.parts):
                continue
            if path.suffix in (".json", ".py") and path.is_file():
                keluar.append(path)
    return sorted(set(keluar))


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="Larangan kosakata saran finansial [K5]")
    ap.add_argument("--paths", nargs="*", default=None,
                    help="berkas/direktori; bawaan: keluaran + kode")
    args = ap.parse_args(argv)

    if args.paths:
        bases = [Path(p) for p in args.paths]
    else:
        bases = [ROOT / p for p in (*TARGET_JSON, *TARGET_PY)]
    bases = [b for b in bases if b.exists()]

    # vocab_guard.py sendiri mendaftarkan kata terlarang — memeriksanya akan
    # selalu merah, dan itu bukan temuan.
    diperiksa = [p for p in kumpulkan(bases) if p.resolve() != Path(__file__).resolve()]

    pelanggaran: list[Pelanggaran] = []
    for path in diperiksa:
        pelanggaran += (periksa_json if path.suffix == ".json" else periksa_python)(path)

    print(f"larangan kosakata: {len(diperiksa)} berkas diperiksa")
    if not pelanggaran:
        print("bersih.")
        return 0

    print(f"\n{len(pelanggaran)} pelanggaran:\n")
    for p in pelanggaran:
        print(p)
    print("\nAturan main: PANTAU melaporkan pola, tidak menyuruh orang bertransaksi. "
          "Tulis ulang jadi deskripsi, bukan ajakan. [K5]")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
