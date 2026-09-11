import { loadIndex, loadInvestigation } from "@/lib/transcript";
import "./metodologi.css";

const COMPONENTS = [
  { code: "BCI", name: "Broker Concentration Index", q: "Berapa persen net buy dikuasai 3 broker teratas? (HHI)", src: "fetch-broker-summary-top" },
  { code: "VAS", name: "Volume Anomaly Score", q: "Volume hari ini berapa sigma di atas baseline 90 hari?", src: "fetch-daily-transaction" },
  { code: "PFD", name: "Price–Fundamental Divergence", q: "Harga naik tajam sementara laba flat/rugi?", src: "fetch-quarterly-financials" },
  { code: "FFS", name: "Free Float Scarcity", q: "Berapa kecil saham yang benar-benar beredar?", src: "fetch-free-float" },
  { code: "FRD", name: "Foreign–Retail Divergence", q: "Asing keluar saat harga naik = distribusi ke ritel?", src: "fetch-foreign-flow" },
  { code: "SSS", name: "Structural Signal Score", q: "Pernah disuspend? Rights issue beruntun? Insider jual?", src: "fetch-suspensions" },
] as const;

const BANDS = [
  { range: "0–29", txt: "Normal — tidak ada pola tidak biasa terdeteksi", color: "var(--sig-normal)" },
  { range: "30–59", txt: "Perlu diperhatikan — ada beberapa pola yang layak dicermati", color: "var(--sig-watch)" },
  { range: "60–79", txt: "Waspada — beberapa indikator menunjukkan pola tidak biasa", color: "var(--sig-alert)" },
  { range: "80–100", txt: "Sangat waspada — banyak indikator tidak biasa secara bersamaan", color: "var(--sig-danger)" },
];

function latestWeights(): { weights: Map<string, number>; version: string | null } {
  const index = loadIndex();
  const latest = [...index.investigations].sort((a, b) => b.as_of.localeCompare(a.as_of))[0];
  if (!latest) return { weights: new Map(), version: null };
  try {
    const t = loadInvestigation(latest.id);
    return { weights: new Map(t.components.map((c) => [c.code, c.weight])), version: t.weights_version };
  } catch {
    return { weights: new Map(), version: null };
  }
}

export default function MetodologiPage() {
  const { weights, version } = latestWeights();

  return (
    <main>
      <div className="sec-label"><h2>Metodologi</h2><span className="n">// bagaimana skor dibangun</span></div>

      <p className="method-lede">
        Agen memutuskan <b>apa</b> yang diselidiki; kode memutuskan <b>berapa</b> skornya. Enam sub-skor
        deterministik (0–100), tanpa LLM di jalur perhitungan. Narasi divalidasi sitasi — angka tanpa padanan
        di buku bukti otomatis ditolak.
      </p>
      <div className="formula">
        PANTAU = Σ (wᵢ · sub_skorᵢ) / Σ wᵢ <span className="muted"> — hanya atas komponen yang benar-benar diselidiki</span><br />
        confidence = Σ wᵢ <span className="muted">(bobot komponen yang tercakup) → investigasi 2 langkah = keyakinan rendah, dinyatakan terang-terangan</span>
      </div>

      <section>
        <div className="sec-label">
          <h2>Enam komponen</h2>
          <span className="n">// bobot {version ? `kalibrasi ${version}` : "menunggu kalibrasi"}</span>
        </div>
        <div className="panel" style={{ padding: "6px 16px" }}>
          {COMPONENTS.map((c) => {
            const w = weights.get(c.code);
            return (
              <div className="comp" key={c.code}>
                <div className="code">{c.code}</div>
                <div>
                  <div className="cname">{c.name}</div>
                  <div className="cq">{c.q}</div>
                  <div className="cfoot">
                    <span className="csrc">{c.src}</span>
                    <span className="cw">
                      bobot {w != null ? w.toFixed(2) : "—"}
                      <span className="bar"><i style={{ width: `${(w ?? 0) * 100 * 2.5}%` }} /></span>
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <div className="sec-label"><h2>Band interpretasi</h2><span className="n">// ambang</span></div>
        <div className="bands">
          {BANDS.map((b) => (
            <div className="brow" key={b.range}>
              <span className="range" style={{ color: b.color }}>{b.range}</span>
              <span className="txt">{b.txt}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="sec-label"><h2>Dua angka validasi</h2><span className="n">// ini yang bikin menang</span></div>
        <div className="vgrid">
          <div className="valcard">
            <div className="vh">
              <div className="q">Angka 1</div>
              <div className="title">Apakah skornya berarti?</div>
            </div>
            <div className="vb">
              <Metric label="Precision@20" value="0,45" tgt="bagian uji 0,32 · k=20" />
              <Metric label="Recall pada ambang ≥60" value="0,33" tgt="bagian uji 0,33" />
              <Metric label="Median lead time" value="5,0 hari" tgt="bagian uji 7,5 · sebelum suspensi" />
              <div className="vnote">
                <b>Provisional.</b> Sampel kecil (9 positif / 22 kontrol dari warehouse yang di-commit); Precision@20 di sini
                mendekati proporsi positif — bukti pipa perhitungan jalan, bukan klaim performa. Sumber:{" "}
                <b>reports/validation.md</b> (2026-09-10, split-waktu).
              </div>
            </div>
          </div>
          <div className="valcard">
            <div className="vh">
              <div className="q">Angka 2</div>
              <div className="title">Apakah agennya berarti?</div>
            </div>
            <div className="vb">
              <Metric label="Hemat kredit vs investigasi menyeluruh" tgt="target ≥ 50%" />
              <Metric label="Kesepakatan band vs baseline" tgt="target ≥ 90%" />
              <Metric label="Presisi eskalasi" tgt="probe di luar rencana yang mengubah band" />
              <Metric label="Ablasi vs urutan tetap & acak" tgt="agen harus mengalahkan keduanya" />
              <div className="vnote"><b>Menunggu eval agen</b> — <b>evals/</b> belum dijalankan.</div>
            </div>
          </div>
        </div>
        <div className="pending-note">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" strokeLinecap="round" />
          </svg>
          <span>
            Angka 1 sudah dari kalibrasi split-waktu tapi <b style={{ color: "var(--text)" }}>provisional</b> (sampel kecil).
            Angka 2 menyusul dari <b style={{ color: "var(--text)" }}>evals/</b> (agen vs menyeluruh vs ablasi). Ditampilkan apa adanya, termasuk kalau mengecewakan.
          </span>
        </div>
      </section>

      <section>
        <div className="sec-label"><h2>Batasan yang diakui terbuka</h2><span className="n">// kejujuran = kredibilitas</span></div>
        <div className="limits">
          <div className="limit"><span className="m">01</span><span><b>Suspensi bukan sinonim manipulasi.</b> Himpunan positif kecil; suspensi karena pergerakan tidak wajar hanya proksi terdekat, bukan label sempurna.</span></div>
          <div className="limit"><span className="m">02</span><span><b>FFS bukan point-in-time historis.</b> Sectors hanya menyediakan free float terkini, jadi FFS berperan sebagai sinyal keadaan-terkini — bukan komponen berkalibrasi lintas waktu.</span></div>
          <div className="limit"><span className="m">03</span><span><b>Data EOD, ada keterlambatan.</b> Semua angka bertanda <code className="mono">as_of</code> WIB dan ditampilkan apa adanya — kami tidak berpura-pura real-time.</span></div>
          <div className="limit"><span className="m">04</span><span><b>Bobot berversi.</b> Tiap transkrip membawa <code className="mono">weights_version</code>; skor lama tidak tercampur dengan bobot baru.</span></div>
        </div>
      </section>

      <div className="disclaimer">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <circle cx="12" cy="12" r="9.5" /><path d="M12 8v5" strokeLinecap="round" /><circle cx="12" cy="16.4" r="0.4" fill="currentColor" stroke="none" />
        </svg>
        PANTAU adalah alat informasi dan analisis, bukan saran investasi.
      </div>
    </main>
  );
}

function Metric({ label, tgt, value }: { label: string; tgt: string; value?: string }) {
  return (
    <div className="metric">
      <div className="ml">{label}</div>
      <div className="mr">
        <div className={value ? "val" : "val pending"}>{value ?? "—"}</div>
        <div className="tgt">{tgt}</div>
      </div>
    </div>
  );
}
