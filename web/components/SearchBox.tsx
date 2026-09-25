"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

const REPO = "https://github.com/hamzadlnitb/sectors2026";

/** Hero search. Ticker yang punya investigasi → buka investigasinya. Ticker yang
 *  belum pernah diselidiki → tawarkan "minta agen selidiki" lewat GitHub Issue
 *  (jalur permintaan T3: nol backend, tetap otonom, tercatat). */
export default function SearchBox({ routes }: { routes: Record<string, string> }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [miss, setMiss] = useState<{ sym: string; short: boolean } | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    const sym = q.trim().toUpperCase();
    if (!sym) return;
    const id = routes[sym];
    if (id) {
      setMiss(null);
      router.push(`/investigasi/${id}`);
    } else {
      setMiss({ sym, short: sym.length < 4 });
    }
  }

  const issueUrl =
    miss && !miss.short
      ? `${REPO}/issues/new?template=selidiki.yml&title=${encodeURIComponent(`selidiki: ${miss.sym}`)}`
      : "";

  return (
    <div className="searchwrap">
      <form className="search" onSubmit={submit}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="7" />
          <path d="M20 20l-4.5-4.5" strokeLinecap="round" />
        </svg>
        <input
          type="text"
          placeholder="Masukkan kode saham IDX…"
          aria-label="Kode saham IDX"
          spellCheck={false}
          value={q}
          onChange={(e) => { setQ(e.target.value.toUpperCase().slice(0, 4)); setMiss(null); }}
        />
        <button type="submit">Investigasi →</button>
      </form>

      {miss && (
        <div className="search-miss" role="status">
          {miss.short ? (
            <span>Kode saham IDX terdiri dari 4 huruf, mis. <b>BBCA</b>.</span>
          ) : (
            <span>
              <b>{miss.sym}</b> belum pernah diselidiki.{" "}
              <a href={issueUrl} target="_blank" rel="noopener noreferrer">
                Minta agen menyelidiki →
              </a>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
