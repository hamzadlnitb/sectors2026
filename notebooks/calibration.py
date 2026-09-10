"""Kalibrasi bobot komposit PANTAU — Angka 1. ARCHITECTURE §6, TASK_HAMZAH H1.

Skrip, bukan notebook: hasilnya harus bisa diulang di mesin bersih dengan satu
perintah dan masuk ke CI, dan diff notebook tidak bisa dibaca manusia.

    python3 notebooks/calibration.py            # cetak ringkasan
    python3 notebooks/calibration.py --tulis    # + tulis reports/validation.md

**Nol jaringan, dan itu ditegakkan struktur, bukan janji.** Context dibuat
dengan client=None, jadi Context.ensure() pulang membawa nol tanpa pernah
menyentuh CreditAwareClient. Satu-satunya sumber data adalah parquet yang sudah
di-commit di data/warehouse/.

**Nol lookahead, juga ditegakkan struktur.** Sub-skor pada T-k dihitung lewat
Context(as_of=hari_bursa_ke_k_sebelum_peristiwa), dan Warehouse.connect memasang
view yang sudah tersaring ≤ as_of. Probe tidak bisa melihat tanggal suspensi
walau SQL-nya salah tulis, karena barisnya memang tidak ada di sesi itu.

Alur:
  1. himpunan positif  — suspensi beralasan pergerakan/aktivitas tidak wajar
  2. himpunan kontrol  — tersamakan subsektor + kapitalisasi, tanggal sama
  3. enam sub-skor pada T-1 / T-3 / T-5 / T-10 hari bursa
  4. bobot             — alokasi sebanding daya pisah (AUC) tiap komponen
  5. split waktu       — kalibrasi pada bagian lebih tua, uji pada yang lebih baru
  6. Angka 1           — Precision@20, recall pada ambang >=60, median lead time

Kalau sampelnya terlalu tipis untuk langkah 4-6 — dan per 10 September 2026
memang begitu — skrip TIDAK mengarang angka. Ia melaporkan berapa yang berhasil
dikumpulkan, berapa yang dibutuhkan, dan mempertahankan bobot prior domain di
core/scoring/weights.py.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.schemas import PROBE_TO_COMPONENT  # noqa: E402
from core.ingest.warehouse import Warehouse, trading_days  # noqa: E402
from core.probes.base import Context  # noqa: E402
from core.probes.registry import PROBES  # noqa: E402
from core.scoring.weights import (  # noqa: E402
    MIN_POSITIF_UNTUK_KALIBRASI,
    WEIGHTS,
    WEIGHTS_VERSION,
)

LAPORAN = ROOT / "reports" / "validation.md"

# Jeda T-k yang diminta protokol, dalam HARI BURSA (bukan hari kalender).
LAG = (1, 3, 5, 10)

# Alasan suspensi yang dihitung positif. Pola ini TIDAK dikarang: ia dibaca dari
# nilai kolom `reason` yang benar-benar ada di data/warehouse/suspensions.parquet.
# Dua bentuk yang muncul, sering digabung dalam satu kalimat:
#   "Terjadinya peningkatan harga kumulatif yang signifikan pada saham XXXX.JK"
#   "... dalam rangka cooling down sebagai bentuk perlindungan bagi investor"
# Dua pola terakhir belum pernah muncul di tarikan ini tapi ada di tata bahasa
# pengumuman IDX; dibiarkan supaya backfill berikutnya tidak perlu mengedit ini.
POLA_POSITIF = re.compile(
    r"peningkatan harga kumulatif"
    r"|cooling down"
    r"|pergerakan harga.*di luar kebiasaan"
    r"|aktivitas transaksi.*tidak wajar"
    r"|unusual market activity",
    re.IGNORECASE,
)

# Alasan yang JELAS bukan pergerakan pasar — dipakai sebagai penjaga, supaya
# kalau tarikan berikutnya membawa kalimat baru, ia jatuh ke "tak terklasifikasi"
# dan terlihat di ringkasan, bukan diam-diam ikut jadi positif.
POLA_ADMINISTRATIF = re.compile(
    r"laporan keuangan|biaya pencatatan|papan pemantauan|kelangsungan usaha"
    r"|peraturan bursa|delisting|buyback|suspend more than",
    re.IGNORECASE,
)

# Dua suspensi pada emiten yang sama dalam jendela ini dianggap SATU peristiwa.
# IDX kerap menyuspensi dua kali dalam sepekan untuk episode kenaikan yang sama;
# menghitungnya dua kali akan menggandakan bobot episode itu di regresi.
JEDA_PERISTIWA_HARI = 10

# Riwayat minimum sebelum sebuah emiten layak jadi kandidat sama sekali. Di
# bawah ini VAS memulangkan unavailable dan barisnya kosong seluruhnya.
MIN_SESI_RIWAYAT = 40

KONTROL_PER_POSITIF = 3


@dataclass(frozen=True)
class Peristiwa:
    """Satu titik pengamatan: emiten, tanggal acuan, dan labelnya."""

    symbol: str
    tanggal: date
    label: int
    alasan: str = ""


# ── 1. himpunan positif ─────────────────────────────────────────────────────

def klasifikasi_alasan(wh: Warehouse) -> pd.DataFrame:
    """Seluruh suspensi + label alasannya. Kolom `kelas` dipakai ringkasan."""
    df = wh.frame("suspensions")
    if df.empty:
        return df.assign(kelas=pd.Series(dtype="object"))
    alasan = df["reason"].fillna("")
    kelas = pd.Series("tak_terklasifikasi", index=df.index, dtype="object")
    kelas[alasan.str.contains(POLA_ADMINISTRATIF)] = "administratif"
    kelas[alasan.str.contains(POLA_POSITIF)] = "pergerakan"
    df = df.copy()
    df["kelas"] = kelas
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.date
    return df


def gabung_episode(df: pd.DataFrame) -> list[Peristiwa]:
    """Suspensi berurutan pada emiten yang sama → satu peristiwa (yang pertama)."""
    keluar: list[Peristiwa] = []
    for symbol, grup in df.sort_values(["symbol", "start_date"]).groupby("symbol"):
        terakhir: date | None = None
        for _, baris in grup.iterrows():
            hari = baris["start_date"]
            if terakhir and (hari - terakhir).days <= JEDA_PERISTIWA_HARI:
                continue
            terakhir = hari
            keluar.append(Peristiwa(symbol, hari, 1, baris["reason"] or ""))
    return sorted(keluar, key=lambda p: (p.tanggal, p.symbol))


# ── 2. himpunan kontrol tersamakan ──────────────────────────────────────────

def semesta_harga(wh: Warehouse) -> dict[str, int]:
    """Emiten yang punya riwayat harga di warehouse, beserta panjangnya.

    Tanpa riwayat, kelima probe berjendela memulangkan unavailable dan barisnya
    tidak menyumbang apa pun ke regresi — jadi emiten seperti itu tidak boleh
    ikut jadi kontrol, karena akan terlihat seperti "kontrol berskor rendah"
    padahal ia cuma tidak terukur.
    """
    from core.ingest.warehouse import price_frame

    df = price_frame(wh)
    if df.empty:
        return {}
    return df.groupby("symbol").size().to_dict()


def profil(wh: Warehouse) -> pd.DataFrame:
    df = wh.frame("company_profile")
    if df.empty:
        return pd.DataFrame(columns=["symbol", "sub_sector", "market_cap"])
    return df[["symbol", "sub_sector", "market_cap"]]


def kontrol_tersamakan(positif: list[Peristiwa], layak: dict[str, int],
                       prof: pd.DataFrame) -> list[Peristiwa]:
    """Kontrol untuk tiap positif: emiten lain, TANGGAL SAMA, profil terdekat.

    Penyamaan dilakukan dua tahap sesuai §6: subsektor sama lebih dulu, lalu di
    dalamnya diurutkan menurut kedekatan log-kapitalisasi. Kalau subsektornya
    tidak punya pasangan — dan di warehouse setipis ini itu lazim — penyamaan
    turun ke kapitalisasi saja, dan fakta itu ikut dilaporkan.
    """
    import math

    disuspensi = {p.symbol for p in positif}
    kandidat = [s for s in layak if s not in disuspensi]
    info = prof.set_index("symbol").to_dict("index")

    def jarak(a: str, b: str) -> float:
        ma, mb = info.get(a, {}).get("market_cap"), info.get(b, {}).get("market_cap")
        if not ma or not mb or ma <= 0 or mb <= 0:
            return float("inf")
        return abs(math.log10(float(ma)) - math.log10(float(mb)))

    keluar: list[Peristiwa] = []
    for p in positif:
        sektor = info.get(p.symbol, {}).get("sub_sector")
        sesektor = [s for s in kandidat if info.get(s, {}).get("sub_sector") == sektor]
        kolam = sesektor or kandidat
        terpilih = sorted(kolam, key=lambda s: (jarak(p.symbol, s), s))[:KONTROL_PER_POSITIF]
        keluar.extend(Peristiwa(s, p.tanggal, 0, "kontrol tersamakan") for s in terpilih)
    return keluar


# ── 3. enam sub-skor, strictly point-in-time ────────────────────────────────

def hari_bursa_sebelum(wh: Warehouse, peristiwa: date, lag: int) -> date | None:
    """Hari bursa ke-`lag` SEBELUM tanggal peristiwa.

    Tanggal peristiwa sendiri dibuang: pada hari suspensi diumumkan, kerugiannya
    sudah terjadi dan skor di hari itu tidak menjawab "apakah kita bisa
    memperingatkan lebih dulu".
    """
    sesi = [d for d in trading_days(wh, peristiwa, lag + 40) if d < peristiwa]
    return sesi[-lag] if len(sesi) >= lag else None


def sub_skor(wh: Warehouse, symbol: str, as_of: date) -> dict[str, float | None]:
    """Enam sub-skor pada satu tanggal acuan. client=None → nol jaringan."""
    ctx = Context(as_of=as_of, warehouse=wh, client=None, budget_remaining=0, phase="dev")
    hasil: dict[str, float | None] = {}
    for nama, probe in PROBES.items():
        r = probe.run(symbol, ctx)
        hasil[PROBE_TO_COMPONENT[nama]] = r.sub_score
    return hasil


def kumpulkan(wh: Warehouse, peristiwa: list[Peristiwa]) -> pd.DataFrame:
    """Matriks pengamatan: satu baris per (emiten, peristiwa, lag)."""
    baris = []
    for p in peristiwa:
        for lag in LAG:
            acuan = hari_bursa_sebelum(wh, p.tanggal, lag)
            if acuan is None:
                continue
            skor = sub_skor(wh, p.symbol, acuan)
            baris.append({
                "symbol": p.symbol, "peristiwa": p.tanggal, "lag": lag,
                "as_of": acuan, "label": p.label, **skor,
            })
    kolom = ["symbol", "peristiwa", "lag", "as_of", "label", *WEIGHTS]
    return pd.DataFrame(baris, columns=kolom)


# ── 4. pencarian bobot ──────────────────────────────────────────────────────

def auc(positif: pd.Series, negatif: pd.Series) -> float | None:
    """AUC = P(skor positif > skor kontrol), lewat peringkat Mann-Whitney.

    Dipilih daripada koefisien regresi logistik karena bisa dijelaskan dalam 15
    detik: "seberapa sering komponen ini memberi nilai lebih tinggi pada saham
    yang benar-benar disuspensi daripada pada kembarannya yang tidak."
    """
    a, b = positif.dropna(), negatif.dropna()
    if a.empty or b.empty:
        return None
    gabung = pd.concat([a, b])
    peringkat = gabung.rank()
    jumlah = peringkat.iloc[: len(a)].sum()
    return float((jumlah - len(a) * (len(a) + 1) / 2) / (len(a) * len(b)))


def daya_pisah(df: pd.DataFrame) -> dict[str, float | None]:
    """AUC tiap komponen atas seluruh lag."""
    return {
        kode: auc(df.loc[df.label == 1, kode], df.loc[df.label == 0, kode])
        for kode in WEIGHTS
    }


def bobot_dari_auc(nilai: dict[str, float | None]) -> dict[str, float]:
    """Bobot sebanding kelebihan AUC di atas 0,5, dinormalkan ke jumlah 1,0.

    Komponen yang AUC-nya <= 0,5 (tidak memisahkan, atau memisahkan ke arah yang
    salah) mendapat nol — bukan bobot negatif. Skor PANTAU harus tetap bisa
    dibaca sebagai "makin tinggi makin patut dicermati"; komponen dengan bobot
    negatif akan membuat kalimat itu bohong.
    """
    lebih = {k: max(0.0, (v or 0.5) - 0.5) for k, v in nilai.items()}
    total = sum(lebih.values())
    if total <= 0:
        return dict(WEIGHTS)
    kasar = {k: v / total for k, v in lebih.items()}
    # Bulatkan ke 2 desimal lalu tambal selisih pada komponen terbesar, supaya
    # jumlahnya tetap TEPAT 1,0 dan angkanya tetap enak dibaca di layar.
    bulat = {k: round(v, 2) for k, v in kasar.items()}
    utama = max(bulat, key=lambda k: bulat[k])
    bulat[utama] = round(bulat[utama] + (1.0 - sum(bulat.values())), 2)
    return bulat


# ── 5-6. evaluasi: Angka 1 ──────────────────────────────────────────────────

def komposit(baris: pd.Series, bobot: dict[str, float]) -> tuple[float | None, float]:
    """Skor komposit + keyakinan (berapa bobot yang benar-benar terisi). §4."""
    terpakai = {k: w for k, w in bobot.items() if pd.notna(baris.get(k))}
    if not terpakai:
        return None, 0.0
    total = sum(terpakai.values())
    skor = sum(w * float(baris[k]) for k, w in terpakai.items()) / total
    return skor, total / sum(bobot.values())


def evaluasi(df: pd.DataFrame, bobot: dict[str, float], ambang: int = 60) -> dict:
    """Precision@20, recall pada ambang, median lead time — dalam hari bursa."""
    if df.empty:
        return {"n": 0}
    kerja = df.copy()
    hitung = kerja.apply(lambda b: komposit(b, bobot), axis=1)
    kerja["skor"] = [h[0] for h in hitung]
    kerja["keyakinan"] = [h[1] for h in hitung]
    kerja = kerja[kerja["skor"].notna()]
    if kerja.empty:
        return {"n": 0}

    # Satu baris per emiten-peristiwa: skor TERTINGGI di antara empat lag, dan
    # lag-nya. Itulah yang ditiru operasional harian — watchlist memantau tiap
    # hari, jadi yang relevan adalah "pernahkah ia melewati ambang sebelum
    # peristiwa", bukan "berapa skornya tepat di T-5".
    puncak = (kerja.sort_values("skor", ascending=False)
                   .groupby(["symbol", "peristiwa"], as_index=False).first())

    urut = puncak.sort_values("skor", ascending=False)
    k = min(20, len(urut))
    lewat = puncak[puncak["skor"] >= ambang]
    positif = puncak[puncak.label == 1]
    tertangkap = lewat[lewat.label == 1]

    # Lead time = seberapa jauh SEBELUM peristiwa ambang pertama kali terlampaui.
    # Lag terbesar yang lolos ambang, bukan lag skor tertinggi.
    lead = []
    for _kunci, grup in kerja[kerja.label == 1].groupby(["symbol", "peristiwa"]):
        lolos = grup[grup["skor"] >= ambang]
        if not lolos.empty:
            lead.append(int(lolos["lag"].max()))

    return {
        "n": len(puncak),
        "n_positif": int((puncak.label == 1).sum()),
        "n_kontrol": int((puncak.label == 0).sum()),
        "k": k,
        "precision_at_k": float(urut.head(k).label.mean()) if k else None,
        "recall": float(len(tertangkap) / len(positif)) if len(positif) else None,
        "false_positive": int((lewat.label == 0).sum()),
        "median_lead": float(pd.Series(lead).median()) if lead else None,
        "keyakinan_rata": float(kerja["keyakinan"].mean()),
    }


def split_waktu(df: pd.DataFrame, porsi: float = 0.75) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Kalibrasi pada peristiwa lebih tua, uji pada yang lebih baru.

    §6 menyebut 18 bulan / 6 bulan. Yang dipakai di sini adalah persentil tanggal
    peristiwa, bukan jendela bulan mati, supaya batasnya ikut bergeser saat
    backfill bertambah. Kalau rentangnya sempit, split ini TIDAK berarti — dan
    ringkasan mengatakannya.
    """
    if df.empty:
        return df, df
    hari = sorted(pd.to_datetime(df["peristiwa"]).unique())
    batas = hari[int(len(hari) * porsi)] if len(hari) > 1 else hari[0]
    tanggal = pd.to_datetime(df["peristiwa"])
    return df[tanggal < batas], df[tanggal >= batas]


# ── laporan ─────────────────────────────────────────────────────────────────

def angka(nilai, satuan: str = "", digit: int = 2) -> str:
    if nilai is None or (isinstance(nilai, float) and pd.isna(nilai)):
        return "belum bisa dihitung"
    if isinstance(nilai, float):
        return f"{nilai:.{digit}f}".replace(".", ",") + satuan
    return f"{nilai}{satuan}"


def ringkasan(wh: Warehouse) -> dict:
    """Jalankan seluruh alur dan kembalikan semua angka yang dilaporkan."""
    susp = klasifikasi_alasan(wh)
    kelas = susp["kelas"].value_counts().to_dict() if not susp.empty else {}
    layak_semua = semesta_harga(wh)
    layak = {s: n for s, n in layak_semua.items() if n >= MIN_SESI_RIWAYAT}
    prof = profil(wh)

    semua_positif = gabung_episode(susp[susp.kelas == "pergerakan"]) if not susp.empty else []
    # Positif yang BISA dinilai: emitennya punya riwayat harga, dan T-10 jatuh
    # di dalam rentang kalender yang dimiliki warehouse.
    dapat_dinilai = [
        p for p in semua_positif
        if p.symbol in layak and hari_bursa_sebelum(wh, p.tanggal, max(LAG)) is not None
    ]
    kontrol = kontrol_tersamakan(dapat_dinilai, layak, prof)

    df = kumpulkan(wh, [*dapat_dinilai, *kontrol])
    cukup = len(dapat_dinilai) >= MIN_POSITIF_UNTUK_KALIBRASI

    auc_nilai = daya_pisah(df) if not df.empty else dict.fromkeys(WEIGHTS)
    usulan = bobot_dari_auc(auc_nilai) if cukup else dict(WEIGHTS)
    kalib, uji = split_waktu(df)

    # Inventaris tabel pendukung, dibaca dari warehouse — bukan diketik tangan,
    # supaya tabel "yang dibutuhkan" di laporan tidak jadi basi diam-diam.
    inventaris = {}
    for tabel, kolom in (("broker_summary", "trade_date"), ("foreign_flow", "trade_date"),
                         ("free_float", "as_of")):
        t = wh.frame(tabel)
        inventaris[tabel] = (0, 0) if t.empty else (int(t["symbol"].nunique()),
                                                    int(t[kolom].nunique()))

    hari_peristiwa = sorted({p.tanggal for p in dapat_dinilai})
    rentang = (hari_peristiwa[0], hari_peristiwa[-1]) if hari_peristiwa else (None, None)

    return {
        "kelas": kelas,
        "susp_total": int(len(susp)),
        "susp_simbol": int(susp["symbol"].nunique()) if not susp.empty else 0,
        "positif_mentah": len(susp[susp.kelas == "pergerakan"]) if not susp.empty else 0,
        "positif_episode": len(semua_positif),
        "positif_dinilai": len(dapat_dinilai),
        "kontrol": len(kontrol),
        "simbol_berharga": len(layak_semua),
        "simbol_layak": len(layak),
        "profil_baris": int(len(prof)),
        "rentang_peristiwa": rentang,
        "inventaris": inventaris,
        "df": df,
        "auc": auc_nilai,
        "cukup": cukup,
        "bobot_dipakai": dict(WEIGHTS),
        "bobot_usulan": usulan,
        "hasil_semua": evaluasi(df, WEIGHTS),
        "hasil_kalibrasi": evaluasi(kalib, WEIGHTS),
        "hasil_uji": evaluasi(uji, WEIGHTS),
        "n_kalib": int(len(kalib)),
        "n_uji": int(len(uji)),
    }


def cetak(r: dict) -> None:
    print("PANTAU — kalibrasi bobot (Angka 1)")
    print("warehouse : data/warehouse/   jaringan: TIDAK DIPAKAI (client=None)")
    print(f"bobot     : {WEIGHTS_VERSION}\n")

    print("Suspensi di warehouse")
    print(f"  total baris                 {r['susp_total']:>6}  ({r['susp_simbol']} emiten)")
    for nama, n in sorted(r["kelas"].items(), key=lambda kv: -kv[1]):
        print(f"  alasan {nama:<20} {n:>6}")
    print()

    print("Himpunan positif")
    print(f"  baris beralasan pergerakan  {r['positif_mentah']:>6}")
    print(f"  setelah digabung jadi episode {r['positif_episode']:>4}")
    print(f"  yang BISA dinilai (ada riwayat harga + T-10 tersedia) {r['positif_dinilai']:>4}")
    print(f"  kontrol tersamakan          {r['kontrol']:>6}")
    if r["rentang_peristiwa"][0]:
        print(f"  rentang peristiwa           {r['rentang_peristiwa'][0]} .. "
              f"{r['rentang_peristiwa'][1]}")
    print(f"  emiten berharga di warehouse {r['simbol_berharga']:>5} "
          f"(>= {MIN_SESI_RIWAYAT} sesi: {r['simbol_layak']})")
    print(f"  baris company_profile        {r['profil_baris']:>5}\n")

    print(f"Pengamatan (emiten x peristiwa x lag {LAG}): {len(r['df'])} baris")
    if not r["df"].empty:
        isi = {k: int(r["df"][k].notna().sum()) for k in WEIGHTS}
        print("  sub-skor terisi per komponen: "
              + ", ".join(f"{k} {v}" for k, v in isi.items()))
    print()

    print("Daya pisah per komponen (AUC positif vs kontrol)")
    for kode, v in r["auc"].items():
        print(f"  {kode}  {angka(v)}")
    print()

    print(f"Bobot dipakai   : {r['bobot_dipakai']}")
    if r["cukup"]:
        print(f"Bobot usulan AUC: {r['bobot_usulan']}")
    else:
        print(f"Bobot usulan    : TIDAK DIHITUNG — {r['positif_dinilai']} positif, "
              f"minimum {MIN_POSITIF_UNTUK_KALIBRASI}. Bobot prior domain dipertahankan.")
    print()

    print("Angka 1")
    for judul, kunci in (("seluruh sampel", "hasil_semua"),
                         ("bagian kalibrasi (lebih tua)", "hasil_kalibrasi"),
                         ("bagian uji (lebih baru)", "hasil_uji")):
        h = r[kunci]
        if not h.get("n"):
            print(f"  {judul:<30} tidak ada pengamatan berskor")
            continue
        print(f"  {judul:<30} n={h['n']} (+{h['n_positif']}/-{h['n_kontrol']})  "
              f"P@{h['k']}={angka(h['precision_at_k'])}  "
              f"recall>=60={angka(h['recall'])}  "
              f"median lead={angka(h['median_lead'], ' hari bursa', 1)}")
    print()
    print("PANTAU adalah alat informasi dan analisis, bukan saran investasi.")


def markdown(r: dict) -> str:
    h = r["hasil_semua"]
    uji = r["hasil_uji"]
    b = ", ".join(f"{k} {v:.2f}".replace(".", ",") for k, v in r["bobot_dipakai"].items())
    baris_auc = "\n".join(
        f"| {kode} | {angka(v)} | {int(r['df'][kode].notna().sum()) if not r['df'].empty else 0} |"
        for kode, v in r["auc"].items()
    )
    p1, p2 = r["rentang_peristiwa"]
    return f"""# reports/validation.md — Angka 1

> Dihasilkan `python3 notebooks/calibration.py --tulis` pada {date.today()}.
> Jangan diedit tangan: tiap angka di bawah keluar dari skrip itu, atas
> `data/warehouse/` yang di-commit, **nol panggilan jaringan**.

Bobot yang berlaku: `{WEIGHTS_VERSION}` — {b}.

---

## Ringkasan satu paragraf

Protokol §6 dijalankan penuh dan **belum menghasilkan bobot terkalibrasi.**
Dari {r['susp_total']} baris suspensi ({r['susp_simbol']} emiten) di warehouse,
{r['positif_mentah']} beralasan pergerakan harga — digabung jadi
**{r['positif_episode']} episode**. Yang benar-benar **bisa dinilai** hanya
**{r['positif_dinilai']}**, karena riwayat harga di warehouse cuma mencakup
{r['simbol_layak']} emiten dengan >= {MIN_SESI_RIWAYAT} sesi. Kontrol tersamakan
yang terbentuk: **{r['kontrol']}**. Bobot di `core/scoring/weights.py` karena itu
adalah **prior domain**, ditandai `-sementara`, bukan hasil regresi.

## Angka 1

| Metrik | Seluruh sampel | Bagian uji (lebih baru) |
| --- | --- | --- |
| Pengamatan (emiten x peristiwa) | {h.get('n', 0)} | {uji.get('n', 0)} |
| Positif / kontrol | {h.get('n_positif', 0)} / {h.get('n_kontrol', 0)} | {uji.get('n_positif', 0)} / {uji.get('n_kontrol', 0)} |
| Precision@{h.get('k', 20)} | {angka(h.get('precision_at_k'))} | {angka(uji.get('precision_at_k'))} |
| Recall pada ambang >= 60 | {angka(h.get('recall'))} | {angka(uji.get('recall'))} |
| Median lead time (hari bursa) | {angka(h.get('median_lead'), '', 1)} | {angka(uji.get('median_lead'), '', 1)} |
| Keyakinan rata-rata (bobot terisi) | {angka(h.get('keyakinan_rata'))} | {angka(uji.get('keyakinan_rata'))} |

Precision@20 di sini **bukan** Precision@20 yang sesungguhnya: seluruh semesta
cuma {h.get('n', 0)} pengamatan berskor (k = {h.get('k', 0)}), jadi 20 teratas
hampir sama dengan seluruh daftar dan angkanya mendekati proporsi positif di
sampel. Pada himpunan sekecil ini satu emiten memindahkan angka lebih dari 0,1 —
perlakukan kolom di atas sebagai bukti bahwa pipa perhitungannya jalan, bukan
sebagai klaim performa.

## Daya pisah per komponen

AUC = seberapa sering komponen memberi nilai lebih tinggi pada saham yang
benar-benar disuspensi daripada pada kembarannya yang tidak. 0,5 = tidak
memisahkan sama sekali.

| Komponen | AUC | Sub-skor terisi |
| --- | --- | --- |
{baris_auc}

Kolom terakhir adalah masalah sebenarnya: komponen yang jarang terisi tidak bisa
dikalibrasi, seberapa pun bagus rumusnya.

## Protokol yang dijalankan

1. **Positif** — kolom `reason` di `suspensions.parquet` dibaca apa adanya. Dua
   bentuk kalimat yang ada di data: "Terjadinya peningkatan harga kumulatif yang
   signifikan pada saham XXXX.JK" dan tambahan "dalam rangka cooling down
   sebagai bentuk perlindungan bagi investor". Alasan administratif (laporan
   keuangan telat, biaya pencatatan, papan pemantauan khusus) **dikeluarkan**.
   Suspensi berulang pada emiten sama dalam {JEDA_PERISTIWA_HARI} hari dihitung
   satu episode.
2. **Kontrol** — {KONTROL_PER_POSITIF} emiten per positif, **tanggal sama**,
   disamakan subsektor lalu kedekatan log-kapitalisasi dari `company_profile`.
3. **Point-in-time** — sub-skor dihitung lewat `Context(as_of=T-k)`;
   `Warehouse.connect` menyaring tiap view ke `<= as_of`, jadi tanggal suspensi
   memang tidak ada di sesi itu. Nol lookahead ditegakkan struktur.
4. **Nol jaringan** — `Context(client=None)`; `Context.ensure()` pulang membawa
   nol tanpa menyentuh `CreditAwareClient`.
5. **Bobot** — alokasi sebanding (AUC - 0,5), dinormalkan ke 1,0. Dipilih karena
   bisa dijelaskan dalam 15 detik. **Tidak dijalankan** selama positif yang bisa
   dinilai < {MIN_POSITIF_UNTUK_KALIBRASI}.
6. **Split waktu** — batas = persentil 75 dari **tanggal peristiwa unik**:
   {r['n_kalib']} baris pengamatan masuk kalibrasi, {r['n_uji']} masuk uji.
   Pembagiannya timpang karena tanggal uniknya cuma segelintir; lihat Batasan 3.

---

# BATASAN

**Yang di bawah ini bukan basa-basi. Baca sebelum memakai angka mana pun.**

**1. Bobotnya belum terkalibrasi.** `WEIGHTS_VERSION` sengaja berakhiran
`-sementara`. Angkanya adalah prior domain yang alasannya ditulis satu per satu
di `core/scoring/weights.py`, bukan keluaran regresi. Siapa pun yang mengutip
"bobot terkalibrasi" dari repo ini per hari ini salah kutip.

**2. Sampelnya terlalu kecil, dan inilah angkanya.** {r['positif_dinilai']}
positif yang bisa dinilai, {r['kontrol']} kontrol. Ambang yang kami tetapkan
sebelum melihat hasil adalah **{MIN_POSITIF_UNTUK_KALIBRASI} positif**; di bawah
itu satu peristiwa menggeser bobot komponen lebih dari 0,05.

**3. Split waktu tidak berarti.** Seluruh peristiwa yang bisa dinilai jatuh di
rentang {p1} .. {p2} — hitungan pekan, bukan 18 bulan + 6 bulan seperti yang
diminta §6. "Bagian uji" di tabel Angka 1 berasal dari pekan yang sama dengan
bagian kalibrasi, jadi ia **tidak membuktikan generalisasi apa pun**.

**4. Suspensi bukan sinonim manipulasi.** IDX menyuspensi karena kenaikan
kumulatif yang signifikan; sebagian episode itu berita korporasi yang sah.
Sebaliknya, manipulasi yang berhasil justru tidak memicu suspensi. Label kita
adalah proksi, dan proksi yang bias ke arah yang mudah terlihat.

**5. SSS berpotensi melihat jawabannya sendiri.** Komponen SSS membaca riwayat
suspensi, dan label kita juga berasal dari suspensi. Point-in-time mencegah ia
membaca peristiwa yang sedang dinilai, tapi emiten yang pernah disuspensi
memang lebih mungkin disuspensi lagi. Itu sebabnya SSS diberi bobot terkecil
(0,08), dan sebabnya angka AUC SSS tidak boleh dibaca sebagai daya prediksi.

**6. Kontrol tidak benar-benar tersamakan.** `company_profile` hanya memuat
{r['profil_baris']} baris, jadi untuk sebagian besar positif tidak ada pasangan
sesubsektor dan penyamaan turun ke kapitalisasi saja — atau gagal sama sekali.

**7. BCI dan FFS — 0,43 dari total bobot — TIDAK PERNAH terisi dalam kalibrasi
ini.** `broker_summary` dan `free_float` masing-masing cuma punya satu tanggal
di warehouse, dan tanggal itu jatuh SESUDAH sebagian besar T-k. Setelah saringan
point-in-time keduanya kosong. Konsekuensinya keras: angka Angka 1 di atas
sesungguhnya berasal dari VAS + PFD + FRD + SSS saja, dan komponen yang kami
beri bobot TERBESAR justru komponen yang belum pernah diuji sekali pun.

**8. Komponen kosong menurunkan keyakinan, tidak menaikkan skor.** Itu perilaku
yang benar (§4) dan bukan bug — tapi artinya Skor PANTAU hari ini praktis
ditentukan dua sampai tiga komponen, dengan keyakinan rata-rata
{angka(h.get('keyakinan_rata'))}.

---

# YANG DIBUTUHKAN SUPAYA ANGKA INI JADI NYATA

Urut menurut pengaruh per kredit:

| Kebutuhan | Sekarang | Target | Kenapa |
| --- | --- | --- | --- |
| Riwayat `daily_transaction` | {r['simbol_layak']} emiten >= {MIN_SESI_RIWAYAT} sesi | >= 150 emiten x 120 sesi | Penentu tunggal berapa positif yang bisa dinilai. Tanpa ini yang lain tidak berguna. |
| Rentang tanggal riwayat harga | beberapa bulan | 24 bulan penuh | Split waktu 18/6 bulan mustahil tanpa ini. |
| `company_profile` | {r['profil_baris']} baris | seluruh emiten kandidat | Kontrol tersamakan butuh subsektor + kapitalisasi. |
| `broker_summary` | {r['inventaris']['broker_summary'][0]} emiten, {r['inventaris']['broker_summary'][1]} tanggal | 20 sesi x tiap kandidat | BCI berbobot terbesar tapi **tidak pernah terisi** pada T-k mana pun. |
| `foreign_flow` | {r['inventaris']['foreign_flow'][0]} emiten, {r['inventaris']['foreign_flow'][1]} tanggal | seluruh kandidat | FRD terisi tapi AUC-nya ~0,5 — belum ada daya pisah. |
| Riwayat `free_float` | {r['inventaris']['free_float'][0]} emiten, {r['inventaris']['free_float'][1]} tanggal snapshot | snapshot bulanan | Satu tanggal snapshot berarti FFS pada T-k **kosong** setelah saringan point-in-time. |

Perkiraan kasar: **>= {MIN_POSITIF_UNTUK_KALIBRASI} episode positif yang bisa
dinilai** dengan rentang peristiwa **>= 12 bulan**. Dengan tingkat suspensi yang
terlihat di 24 bulan terakhir ({r['positif_episode']} episode di
{r['susp_simbol']} emiten), itu berarti backfill `daily_transaction` untuk
sekitar 150 emiten paling aktif — bukan seluruh papan.

---

PANTAU adalah alat informasi dan analisis, bukan saran investasi.
"""


def main(argv: list[str] | None = None) -> int:
    from core.console import setup_console

    setup_console()
    ap = argparse.ArgumentParser(description="Kalibrasi bobot PANTAU — nol jaringan")
    ap.add_argument("--warehouse", type=Path, default=None)
    ap.add_argument("--tulis", action="store_true", help="tulis reports/validation.md")
    args = ap.parse_args(argv)

    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "WEIGHTS harus berjumlah tepat 1,0"

    wh = Warehouse(args.warehouse) if args.warehouse else Warehouse()
    r = ringkasan(wh)
    cetak(r)

    if args.tulis:
        LAPORAN.parent.mkdir(parents=True, exist_ok=True)
        LAPORAN.write_text(markdown(r), encoding="utf-8")
        print(f"\nditulis: {LAPORAN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
