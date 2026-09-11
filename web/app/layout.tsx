import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter, JetBrains_Mono } from "next/font/google";
import TopBar from "@/components/TopBar";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
const jbm = JetBrains_Mono({ variable: "--font-jbm", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "PANTAU — Investigator Saham AI",
  description:
    "AI investigator untuk risiko manipulasi & likuiditas saham IDX — menunjukkan bagaimana ia sampai ke kesimpulan. Alat informasi & analisis, bukan saran investasi.",
};

// Applies a saved theme choice before paint (avoids a flash). No saved choice =
// follow the OS via the media query in globals.css.
const themeInit = `try{var t=localStorage.getItem('pantau-theme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="id" className={`${inter.variable} ${jbm.variable}`}>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <div className="wrap">
          <TopBar />
          {children}
        </div>
      </body>
    </html>
  );
}
