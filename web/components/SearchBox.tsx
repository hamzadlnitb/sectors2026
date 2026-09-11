"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

/** Hero search — routes a ticker to its investigation when one exists,
 *  otherwise to the investigation index. `routes` maps SYMBOL → investigation id. */
export default function SearchBox({ routes }: { routes: Record<string, string> }) {
  const router = useRouter();
  const [q, setQ] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const id = routes[q.trim().toUpperCase()];
    router.push(id ? `/investigasi/${id}` : "/investigasi");
  }

  return (
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
        onChange={(e) => setQ(e.target.value.toUpperCase().slice(0, 4))}
      />
      <button type="submit">Selidiki →</button>
    </form>
  );
}
