import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Halaman tak ditemukan", robots: { index: false } };

export default function NotFound() {
  return (
    <main className="notfound">
      <span className="nf-code mono">404</span>
      <h1>Jejaknya buntu.</h1>
      <p>Halaman atau investigasi yang kamu cari tidak ada, mungkin tickernya belum pernah diselidiki, atau tautannya usang.</p>
      <div className="nf-links">
        <Link href="/" className="nf-primary">← Kembali ke beranda</Link>
        <Link href="/investigasi" className="nf-secondary">Lihat semua investigasi</Link>
      </div>
    </main>
  );
}
