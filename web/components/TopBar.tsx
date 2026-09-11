"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";

const NAV = [
  { href: "/investigasi", label: "Investigasi" },
  { href: "/papan", label: "Papan Waspada" },
  { href: "/metodologi", label: "Metodologi" },
];

export default function TopBar() {
  const pathname = usePathname();
  return (
    <div className="topbar">
      <Link href="/" className="brand" aria-label="PANTAU — beranda">
        <svg width="20" height="20" viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <circle cx="11" cy="11" r="9.2" stroke="var(--accent)" strokeWidth="1.5" />
          <circle cx="11" cy="11" r="4.6" stroke="var(--accent)" strokeWidth="1.5" />
          <circle cx="11" cy="11" r="1.4" fill="var(--accent)" />
          <path d="M11 11 L18.5 11" stroke="var(--accent)" strokeWidth="1.5" />
        </svg>
        PANTAU
      </Link>
      <nav className="nav-links">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={pathname.startsWith(n.href) ? "active" : ""}
          >
            {n.label}
          </Link>
        ))}
      </nav>
      <span className="sp" />
      <div className="spectrum" aria-hidden="true">
        <i style={{ height: 8, background: "var(--sig-normal)" }} />
        <i style={{ height: 12, background: "var(--sig-normal)" }} />
        <i style={{ height: 9, background: "var(--sig-watch)" }} />
        <i style={{ height: 15, background: "var(--sig-watch)" }} />
        <i style={{ height: 11, background: "var(--sig-alert)" }} />
        <i style={{ height: 18, background: "var(--sig-danger)" }} />
        <i style={{ height: 7, background: "var(--sig-alert)" }} />
      </div>
      <ThemeToggle />
    </div>
  );
}
