"use client";

import { useEffect, useState } from "react";

/** Toggles data-theme on <html>, persisting the choice. Defaults follow the OS
 *  until the user picks; the inline script in layout applies a saved choice
 *  before paint to avoid a flash. */
export default function ThemeToggle() {
  const [dark, setDark] = useState(true);

  useEffect(() => {
    const attr = document.documentElement.getAttribute("data-theme");
    const isDark = attr
      ? attr === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    setDark(isDark);
  }, []);

  function flip() {
    const next = dark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("pantau-theme", next);
    } catch {
      /* private mode — ignore */
    }
    setDark(!dark);
  }

  return (
    <button className="toggle" onClick={flip} aria-label="Ganti tema terang/gelap">
      {dark ? <MoonIcon /> : <SunIcon />}
      <span>{dark ? "Dark" : "Light"}</span>
    </button>
  );
}

function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" strokeLinejoin="round" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2.5M12 19v2.5M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2.5 12h2.5M19 12h2.5M4.2 19.8l1.8-1.8M18 6l1.8-1.8" strokeLinecap="round" />
    </svg>
  );
}
