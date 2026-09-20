import type { Metadata } from "next";
import type { ReactNode } from "react";
import { DM_Sans, Inter, JetBrains_Mono } from "next/font/google";
import TopBar from "@/components/TopBar";
import SiteDisclaimer from "@/components/SiteDisclaimer";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
const jbm = JetBrains_Mono({ variable: "--font-jbm", subsets: ["latin"], display: "swap" });
// DM Sans — dipakai retheme landing bergaya Crypgo (di-scope via .lp di landing.css).
const dm = DM_Sans({ variable: "--font-dm", subsets: ["latin"], display: "swap" });

const DESC =
  "AI investigator untuk risiko manipulasi & likuiditas saham IDX — menunjukkan bagaimana ia sampai ke kesimpulan. Alat informasi & analisis, bukan saran investasi.";

export const metadata: Metadata = {
  title: {
    default: "PANTAU — Investigator Saham AI",
    template: "%s · PANTAU",
  },
  description: DESC,
  applicationName: "PANTAU",
  keywords: ["IDX", "saham", "manipulasi pasar", "likuiditas", "AI investigator", "PANTAU", "transparansi"],
  authors: [{ name: "Tim PANTAU" }],
  openGraph: {
    type: "website",
    locale: "id_ID",
    siteName: "PANTAU",
    title: "PANTAU — Investigator Saham AI",
    description: DESC,
  },
  twitter: { card: "summary", title: "PANTAU — Investigator Saham AI", description: DESC },
  robots: { index: true, follow: true },
};

// Applies a saved theme choice before paint (avoids a flash). No saved choice =
// follow the OS via the media query in globals.css.
const themeInit = `try{var t=localStorage.getItem('pantau-theme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="id" className={`${inter.variable} ${jbm.variable} ${dm.variable}`}>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <div className="wrap">
          <TopBar />
          {children}
          <SiteDisclaimer />
        </div>
      </body>
    </html>
  );
}
