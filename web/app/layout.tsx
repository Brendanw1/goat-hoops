import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import { Lato, Be_Vietnam_Pro } from "next/font/google";
import localFont from "next/font/local";
import { Providers } from "@/components/providers";
import "@/styles/globals.css";

/**
 * The same three faces as the baseball sibling, self-hosted for the same
 * reason (app/fonts/README.md has the Wremena provenance and the licensing
 * check). Fonts are the cheapest thing to share between the two apps and the
 * most expensive to get subtly wrong, so this block mirrors goat-pro's.
 */
const lato = Lato({
  subsets: ["latin"],
  weight: ["300", "400", "700", "900"],
  display: "swap",
  variable: "--font-lato",
});

const beVietnamPro = Be_Vietnam_Pro({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
  variable: "--font-be-vietnam-pro",
});

const wremena = localFont({
  src: "./fonts/Wremena-Regular.woff",
  display: "swap",
  preload: false,
  adjustFontFallback: false,
  variable: "--font-wremena",
});

export const metadata: Metadata = {
  title: {
    default: "GOAT-Pro Hoops — NBA research on public data",
    template: "%s — GOAT Hoops",
  },
  description:
    "Public-data basketball research: validated box scores, shot charts, and pre-registered player-impact models for the NBA.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={`dark ${lato.variable} ${beVietnamPro.variable} ${wremena.variable}`}>
      <body>
        {/* Atmospheric fog background — the shared token set from the baseball app */}
        <div className="fog-bg" aria-hidden="true" />
        <Providers>{children}</Providers>
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
