"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/games", label: "Games" },
  { href: "/teams", label: "Teams" },
  { href: "/players", label: "Players" },
  { href: "/stats", label: "Stats" },
  { href: "/alltime", label: "All-Time" },
  { href: "/eras", label: "Eras" },
  { href: "/lineups", label: "Lineups" },
  { href: "/market", label: "Market" },
  { href: "/compare", label: "Compare" },
  { href: "/comps", label: "Comps" },
  { href: "/surplus", label: "Value" },
  { href: "/research", label: "Research" },
  { href: "/about", label: "About" },
] as const;

/**
 * The baseball sibling's origin: env-driven so prod crosses the subdomain and
 * local dev crosses ports with the same code. NEXT_PUBLIC_ is inlined at
 * build; the fallback is the prod subdomain chosen in the two-site decision.
 */
const BASEBALL_URL = process.env.NEXT_PUBLIC_BASEBALL_URL ?? "https://goatpro.dev";

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-40 w-full border-b border-border-subtle bg-black/40 backdrop-blur-md">
      <div className="flex items-center gap-2 px-4 py-2 sm:px-6">
        <Link href="/" aria-label="GOAT-Pro Hoops home"
          className="relative z-10 shrink-0 grid place-items-center w-12 h-12 rounded-full transition-transform duration-200 hover:scale-105 active:scale-95
            shadow-[0_4px_16px_rgba(2,6,12,0.55),0_1px_3px_rgba(2,6,12,0.4)]">
          {/* the basketball: pebbled-orange sphere, four seam curves, the
              wordmark on the leather — read as a ball first, a name second */}
          <svg viewBox="0 0 48 48" className="absolute inset-0 w-full h-full" aria-hidden>
            <defs>
              <radialGradient id="ballLeather" cx="0.34" cy="0.26" r="0.95">
                <stop offset="0%" stopColor="#F98E4C" />
                <stop offset="45%" stopColor="#E56F2E" />
                <stop offset="80%" stopColor="#B84A17" />
                <stop offset="100%" stopColor="#8C3410" />
              </radialGradient>
              <radialGradient id="ballSheen" cx="0.32" cy="0.2" r="0.4">
                <stop offset="0%" stopColor="rgba(255,255,255,0.5)" />
                <stop offset="100%" stopColor="rgba(255,255,255,0)" />
              </radialGradient>
            </defs>
            <circle cx="24" cy="24" r="23" fill="url(#ballLeather)" />
            {/* pebble hint: sparse darker freckles, denser toward the rim */}
            <g fill="rgba(90,30,8,0.35)">
              {[[10, 14], [14, 9], [19, 6], [30, 7], [36, 11], [40, 17], [42, 26],
                [40, 34], [35, 40], [28, 43], [19, 42], [12, 37], [8, 30], [7, 21],
                [16, 30], [13, 25], [34, 30], [37, 22], [30, 40], [11, 20]].map(([x, y], i) => (
                <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 0.7 : 0.5} />
              ))}
            </g>
            {/* the four seams of a basketball */}
            <g stroke="#4A1D07" strokeWidth="1.5" fill="none" opacity="0.9">
              <line x1="24" y1="1.5" x2="24" y2="46.5" />
              <line x1="1.5" y1="24" x2="46.5" y2="24" />
              <path d="M 8 5 C 19 12, 19 36, 8 43" />
              <path d="M 40 5 C 29 12, 29 36, 40 43" />
            </g>
            <circle cx="24" cy="24" r="23" fill="url(#ballSheen)" />
            <circle cx="24" cy="24" r="22.7" fill="none" stroke="rgba(30,12,4,0.55)" strokeWidth="0.6" />
          </svg>
          <span className="relative text-center leading-none drop-shadow-[0_1px_1px_rgba(255,220,180,0.7)]">
            <span className="block text-[12px] font-extrabold tracking-tight text-[#2B1103]">GOAT</span>
            <span className="mt-[3px] block text-[8.5px] font-bold tracking-[0.22em] text-[#3E1A08]">HOOPS</span>
          </span>
        </Link>

        <div className="nav-strip flex w-full min-w-0 items-center gap-0.5 overflow-x-auto pr-2 sm:flex-1 lg:ml-2 xl:ml-4 xl:gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link key={item.href} href={item.href}
                suppressHydrationWarning
                aria-current={isActive ? "page" : undefined}
                className={`
                  relative z-10 shrink-0 whitespace-nowrap px-2.5 py-1.5 rounded-full text-[13px] font-semibold press-scale nav-glow lg:px-3 xl:text-sm 2xl:px-4
                  [text-shadow:0_1px_2px_rgba(10,14,20,0.85)]
                  ${
                    isActive
                      ? "bg-black/45 border border-white/25 text-white"
                      : "text-text-primary/85 hover:text-white hover:bg-black/25"
                  }
                `}>
                {item.label}
              </Link>
            );
          })}
        </div>

        {/* The sport switcher — the seam between the two sites. An <a>, not a
            Link: it leaves this app for the sibling origin entirely. */}
        <a href={BASEBALL_URL}
          className="ml-auto shrink-0 whitespace-nowrap px-2.5 py-1.5 rounded-full text-[12px] font-semibold text-text-primary/70 border border-border-subtle hover:text-white hover:bg-black/25 transition-colors"
          title="Switch to the baseball site">
          Baseball
        </a>
      </div>
    </nav>
  );
}
