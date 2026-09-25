import Link from "next/link";
import SearchBox from "@/components/SearchBox";
import InvestigationCard from "@/components/InvestigationCard";
import ActivityFeed from "@/components/ActivityFeed";
import LandingChat from "@/components/LandingChat";
import { loadIndex, symbolToId } from "@/lib/transcript";
import { loadActivity } from "@/lib/activity";
import "./landing.css";

const PROCESS = [
  { n: "1", w: "Deteksi otomatis", d: "Tiap hari bursa, agen menyapu pasar dan menandai saham yang bergerak tidak wajar, tanpa kamu perlu memantau layar." },
  { n: "2", w: "Selidiki sendiri", d: "Agen memilih bukti mana yang dikejar, menguji tiap dugaan, lalu berhenti begitu buktinya sudah cukup." },
  { n: "3", w: "Jelaskan terbuka", d: "Hasilnya skor plus cerita yang bisa kamu telusuri sampai ke sumber datanya, bukan kotak hitam." },
];

const SIGNALS = [
  { code: "BCI", name: "Konsentrasi broker", d: "Pembelian menumpuk di segelintir broker saja?" },
  { code: "VAS", name: "Anomali volume", d: "Volume melonjak jauh di atas kebiasaannya?" },
  { code: "PFD", name: "Harga vs fundamental", d: "Harga melompat padahal laba datar atau rugi?" },
  { code: "FFS", name: "Saham beredar tipis", d: "Barang langka di pasar sehingga mudah digerakkan?" },
  { code: "FRD", name: "Asing vs ritel", d: "Asing keluar saat harga naik, dilempar ke ritel?" },
  { code: "SSS", name: "Peristiwa struktural", d: "Suspensi, rights issue beruntun, atau insider jual?" },
];

export default function Landing() {
  const index = loadIndex();
  const routes = symbolToId(index);
  const rows = index.investigations.slice(0, 6);
  const flagged = index.investigations.filter((e) => e.band === "waspada" || e.band === "sangat_waspada").length;
  const escalated = index.investigations.filter((e) => e.moments.includes("escalation")).length;
  const activity = loadActivity();

  return (
    <main className="lp">
      <div className="lp-bg" aria-hidden="true">
        <span className="lp-orb a" />
        <span className="lp-orb b" />
        <span className="lp-grid" />
      </div>
      <section className="hero">
        <span className="eyebrow">
          <span className="live" /> Agen investigasi saham IDX
        </span>
        <h1>
          Saham ini ramai. Tapi siapa yang sebenarnya <span className="hl">menggerakkannya</span>?
        </h1>
        <p className="sub">
          PANTAU menyelidiki pergerakan saham seperti analis sungguhan, mengejar bukti,
          menguji dugaan, dan <b>menunjukkan jejaknya sampai kesimpulan</b>.
        </p>
        <SearchBox routes={routes} />
        {rows.length > 0 && (
          <div className="lp-eg">
            <span>Coba lihat:</span>
            {rows.slice(0, 3).map((e) => (
              <Link key={e.id} href={`/investigasi/${e.id}/`} className="eg">{e.symbol}</Link>
            ))}
          </div>
        )}
        <div className="microcopy">
          Setiap temuan bisa kamu telusuri sampai ke buktinya, bukan sekadar angka.
        </div>
      </section>

      <section>
        <div className="lp-head">
          <h2>Cara kerja</h2>
          <p>Dari sinyal mentah sampai kesimpulan yang bisa ditelusuri, dalam tiga langkah.</p>
        </div>
        <div className="process">
          {PROCESS.map((p) => (
            <div className="pstep" key={p.n}>
              <div className="pn">{p.n}</div>
              <div className="pw">{p.w}</div>
              <div className="pd">{p.d}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="lp-head">
          <h2>Yang diperiksa agen</h2>
          <p>Enam pola yang sering muncul saat sebuah saham digerakkan tidak wajar.</p>
        </div>
        <div className="signals">
          {SIGNALS.map((s) => (
            <div className="sig" key={s.code}>
              <span className="sc">{s.code}</span>
              <div>
                <div className="sn">{s.name}</div>
                <div className="sd">{s.d}</div>
              </div>
            </div>
          ))}
        </div>
        <Link href="/metodologi" className="sig-more">Lihat cara agen menghitung skornya →</Link>
      </section>

      <section className="board">
        <div className="board-head">
          <div className="bh-title">
            <h2>Investigasi hari ini</h2>
            <p>Hasil terbaru dari agen, ketuk salah satu untuk lihat jejak lengkapnya.</p>
          </div>
          <div className="board-stats">
            <span><b>{index.investigations.length}</b> diselidiki</span>
            <span><span className="d" style={{ background: "var(--sig-alert)" }} /><b>{flagged}</b> perlu perhatian</span>
            <span><span className="d" style={{ background: "var(--accent)" }} /><b>{escalated}</b> minta jatah tambah</span>
          </div>
        </div>
        <div className="cards">
          {rows.map((e) => (
            <InvestigationCard key={e.id} e={e} />
          ))}
        </div>
        <div className="autobar">
          <span className="ai">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="at">
            Berjalan sendiri, tiap hari bursa pukul <b>17:30 WIB</b>, agen menyapu, menyeleksi, dan menyelidiki tanpa ditunggui.
          </span>
          <Link href="/papan">Lihat Papan Waspada →</Link>
        </div>
      </section>

      <LandingChat items={index.investigations} />

      <ActivityFeed events={activity.events.slice(0, 12)} />

      <div className="footnote">
        Semua ditampilkan dari data yang sudah tersimpan, tanpa panggilan API atau AI saat halaman dibuka.
      </div>
    </main>
  );
}
