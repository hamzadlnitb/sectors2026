"""Validator sitasi: tiap angka di narasi wajib punya padanan di buku bukti. [AD-4]

Klaim yang dijual PANTAU ke juri adalah "halusinasi angka secara struktural
mustahil lolos". Struktural berarti: bukan prompt yang memohon, bukan tinjauan
manusia, tapi daftar-putih. Angka yang tidak ada di buku bukti tidak punya jalan
masuk — narasinya dibuang seluruhnya dan diganti template. [K8][T12]

Cara kerjanya terbalik dari yang biasa: kita tidak mencari angka yang salah,
kita menyusun himpunan angka yang SAH lalu menolak sisanya. Bedanya penting —
penjaga yang mencari pola salah selalu bisa dilewati pola yang belum terpikir.


## Apa yang dianggap "punya padanan"

Untuk tiap `EvidenceEntry`, tiga sumber ikut jadi daftar-putih:

1. `display` — bentuk yang memang dimaksudkan untuk dibaca manusia (`"78%"`,
   `"-Rp 184 M"`, `"14 November 2025"`).
2. `value` — angka mentahnya (`0.78`, `-184000000000`). Narasi boleh menyebut
   salah satu bentuk; keduanya berasal dari probe yang sama.
3. `label` — **ini keputusan yang perlu dijelaskan.** Label memuat angka
   struktural: `"Pangsa net buy 3 broker teratas"`, `"Z-score volume vs baseline
   90 hari"`, `"Rights issue 24 bulan terakhir"`. Narasi yang menulis "3 broker
   teratas" atau "baseline 90 hari" sedang mengutip label, bukan mengarang.
   Label ditulis kode probe dan ikut beku di kontrak — LLM tidak bisa
   menyuntikkan angka ke sana. Menolak angka label akan memaksa fallback pada
   narasi yang justru benar, dan penjaga yang menolak kalimat benar akan
   dimatikan orang dalam seminggu. `fixtures/transcripts/*.json` yang sudah beku
   semuanya bergantung pada aturan ini.

Tidak ada pengecualian lain. Khususnya **tidak ada** pemakluman "angka kecil
boleh lewat": justru di situ karangan paling sering menyelinap ("tiga broker",
"dua kali suspensi"). Narasi yang ingin menyebut bilangan yang tidak ada di buku
bukti harus menulisnya sebagai kata ("tiga", "dua"), dan template kita memang
begitu — kata bukan sitasi, jadi tidak menuntut sumber.


## Format Indonesia yang ditangani

| Bentuk | Contoh | Dinormalkan jadi |
| --- | --- | --- |
| Koma desimal | `4,1σ` | 4.1, satuan σ |
| Titik ribuan | `1.500` | 1500 |
| Persen | `78%`, `78 persen` | 78, satuan % |
| Rupiah berskala | `Rp 184 M`, `Rp 1,2 T` | 184 satuan m; 1.2 satuan t |
| Kelipatan | `1,1×` | 1.1, satuan × |
| Tanggal | `14 November 2025` | 14 dan 2025, tanpa satuan |
| Negatif | `-8%` vs "turun 8%" | 8, satuan % |

**Tanda dibuang, besaran dan satuan tidak.** Bahasa Indonesia menaruh arah di
kata kerja ("turun 8%", "asing keluar bersih Rp 184 M") sementara `display`
menaruhnya di tanda (`-8%`, `-Rp 184 M`). Mencocokkan tanda berarti menolak
kalimat yang benar. Yang dijaga validator ini adalah asal-usul angka, bukan arah
— arah dijaga oleh template pada jalur fallback.

Satuan sebaliknya ikut dicocokkan: `Rp 184 M` dan `Rp 184 T` berbeda seribu
kali, dan tanpa pemeriksaan satuan keduanya akan sama-sama lolos. Satuan yang
tidak dikenali (mis. "hari", "transaksi", "kali") dianggap kosong di kedua sisi,
jadi "90 hari" tetap cocok dengan label "baseline 90 hari".
"""

from __future__ import annotations

import re
from typing import Any

# Satuan yang punya arti kuantitatif. Ditulis eksplisit — kata lain yang
# mengikuti angka ("hari", "transaksi", "broker") bukan satuan, dan diperlakukan
# sama di narasi maupun di bukti, jadi tidak pernah menimbulkan beda.
_SATUAN = {
    "%": "%", "persen": "%",
    "σ": "σ", "sigma": "σ",
    "×": "×", "x": "×",
    "rb": "rb", "ribu": "rb",
    "jt": "jt", "juta": "jt",
    "m": "m", "miliar": "m",
    "t": "t", "triliun": "t",
}

# Singkatan skala rupiah hanya sah dalam huruf besar ("Rp 184 M"). Huruf kecil
# lepas terlalu sering jadi kata biasa untuk dipercaya sebagai satuan.
_POLA_SATUAN = r"%|persen|σ|sigma|×|x|M|T|Jt|jt|juta|miliar|triliun|rb|ribu"

_ANGKA = re.compile(
    r"(?<![\w,.])"                                    # bukan lanjutan token lain
    r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"    # 1.500 / 1.500,25 / 4,1 / 78
    r"(?:\s?(" + _POLA_SATUAN + r")(?!\w))?",         # satuan opsional, tak boleh
)                                                     # jadi awal kata lain


def _besaran(teks: str) -> float:
    """'1.500,25' → 1500.25. Titik ribuan, koma desimal — konvensi Indonesia."""
    if "," in teks:
        return float(teks.replace(".", "").replace(",", "."))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", teks):
        return float(teks.replace(".", ""))
    return float(teks)


def _kunci(besaran: float, satuan: str | None) -> tuple[float, str]:
    return (round(abs(besaran), 6), _SATUAN.get(satuan.lower(), "") if satuan else "")


def _token(teks: str) -> list[tuple[str, tuple[float, str]]]:
    """(potongan asli, kunci) untuk tiap angka dalam satu string."""
    keluar: list[tuple[str, tuple[float, str]]] = []
    for m in _ANGKA.finditer(teks):
        try:
            keluar.append((m.group(0).strip(), _kunci(_besaran(m.group(1)), m.group(2))))
        except ValueError:  # pragma: no cover — regex sudah menjamin bentuknya
            continue
    return keluar


def allowed_keys(evidence: list[Any]) -> set[tuple[float, str]]:
    """Himpunan (besaran, satuan) yang boleh muncul di narasi.

    Dibuka sebagai fungsi publik supaya tes bisa memeriksa daftar-putihnya
    langsung, bukan cuma menyimpulkannya dari hasil akhir.
    """
    sah: set[tuple[float, str]] = set()
    for e in evidence:
        satuan_entri = {""}
        for _, kunci in _token(str(getattr(e, "display", "") or "")):
            sah.add(kunci)
            satuan_entri.add(kunci[1])
        for _, kunci in _token(str(getattr(e, "label", "") or "")):
            sah.add(kunci)

        nilai = getattr(e, "value", None)
        if isinstance(nilai, bool) or nilai is None:
            continue
        if isinstance(nilai, (int, float)):
            # Nilai mentah tidak membawa satuan sendiri; disahkan untuk tiap
            # satuan yang dipakai display entri ini (0.78 ↔ "78%").
            for satuan in satuan_entri:
                sah.add(_kunci(float(nilai), satuan))
        else:
            for _, kunci in _token(str(nilai)):
                sah.add(kunci)
    return sah


def unsupported_numbers(narrative: str, evidence: list[Any]) -> list[str]:
    """Angka di `narrative` yang tidak punya padanan di buku bukti.

    Kosong = narasi boleh dipakai apa adanya. Tidak kosong = narasi dibuang;
    pemanggil (`core.narrative.generate.narrate`) beralih ke template
    deterministik. Tidak ada jalan tengah "perbaiki angkanya", karena angka yang
    salah satu berarti kalimat di sekitarnya juga tidak bisa dipercaya.

    Aturan pencocokan lengkap ada di docstring modul. Ringkasnya: padanan dicari
    ke `display`, `value`, dan `label` tiap `EvidenceEntry`; tanda diabaikan,
    satuan tidak; bilangan yang ditulis sebagai kata ("tiga") bukan sitasi dan
    tidak diperiksa.

    Kembaliannya potongan asli seperti tertulis di narasi ("9,9σ", "500 M"),
    berurut sesuai kemunculan dan tanpa duplikat — supaya log kegagalan
    menunjuk teks yang bisa dicari orang, bukan angka yang sudah dinormalkan.
    """
    sah = allowed_keys(evidence)
    keluar: list[str] = []
    terlihat: set[tuple[float, str]] = set()
    for potongan, kunci in _token(narrative or ""):
        if kunci in sah or kunci in terlihat:
            continue
        terlihat.add(kunci)
        keluar.append(potongan)
    return keluar


# ── nama emiten ─────────────────────────────────────────────────────────────
# Ditambahkan setelah uji end-to-end pertama: MiniMax menghasilkan narasi yang
# setiap angkanya bersumber, tapi menyebut emitennya "JAJA" padahal yang
# diselidiki "JAWA". Validator angka meloloskannya karena memang hanya membaca
# angka. Menyebut emiten yang salah lebih berbahaya daripada angka yang salah:
# pembaca bisa menutup posisi di saham yang keliru, dan juri praktisi pasar akan
# menangkapnya dalam sedetik. [contracts/CHANGES.md C3]

TICKER = re.compile(r"\b[A-Z]{4}\b")

ISTILAH_SAH = frozenset({
    # Singkatan pasar modal Indonesia yang kebetulan berbentuk empat huruf
    # kapital. Bukan daftar lengkap — cukup untuk yang wajar muncul di narasi
    # risiko. Menambah entri di sini melemahkan pemeriksaan, jadi tambahkan
    # hanya kalau istilahnya benar-benar muncul dan benar-benar sah.
    "RUPS",  # rapat umum pemegang saham
    "IUPK",  # izin usaha pertambangan khusus
    "LQ45",  # indeks — walau angkanya membuatnya tak cocok pola, ditulis jelas
    "PANT",  # potongan nama produk kalau tertulis kapital
})


def unsupported_tickers(narrative: str, symbol: str) -> list[str]:
    """Kode emiten empat huruf di narasi yang BUKAN emiten yang diselidiki.

    Kosong = narasi tidak menyebut emiten lain. Pemeriksaan sengaja ketat:
    narasi risiko tidak punya alasan sah menyebut emiten selain yang sedang
    diselidiki, jadi setiap kemunculan diperlakukan sebagai halusinasi sampai
    terbukti sebaliknya lewat ISTILAH_SAH.
    """
    target = symbol.strip().upper()
    asing: list[str] = []
    for kandidat in TICKER.findall(narrative or ""):
        if kandidat == target or kandidat in ISTILAH_SAH:
            continue
        if kandidat not in asing:
            asing.append(kandidat)
    return asing
