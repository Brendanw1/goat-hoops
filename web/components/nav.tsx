"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Games" },
  { href: "/teams", label: "Teams" },
  { href: "/players", label: "Players" },
  { href: "/stats", label: "Stats" },
  { href: "/compare", label: "Compare" },
  { href: "/comps", label: "Comps" },
  { href: "/surplus", label: "Value" },
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
          className="relative z-10 shrink-0 grid place-items-center w-12 h-12 rounded-full transition-transform duration-200 hover:scale-105 active:scale-95 ring-1 ring-slate-900/25
            bg-[linear-gradient(135deg,#ffffff_0%,#f7f9fb_45%,#e7ecf2_100%)]
            shadow-[0_4px_16px_rgba(2,6,12,0.55),0_1px_3px_rgba(2,6,12,0.4),inset_0_-6px_10px_rgba(128,96,60,0.42),inset_0_3px_6px_rgba(255,255,255,0.9),inset_0_0_0_1px_rgba(22,30,44,0.07)]">
          <span aria-hidden className="absolute inset-0 rounded-full
            bg-[radial-gradient(circle_at_30%_24%,rgba(255,255,255,1)_0%,rgba(255,255,255,0)_42%),radial-gradient(circle_at_72%_92%,rgba(232,119,34,0.5)_0%,rgba(232,119,34,0)_50%)]" />
          {/* the ball's seam: one great circle, unlike the baseball's laces */}
          <span aria-hidden className="absolute w-7 h-7 rounded-full border border-[#b45309]/40
            [transform:rotate(-24deg)_scaleY(0.42)]" />
          <span className="relative text-center leading-none">
            <span className="block text-[12px] font-extrabold tracking-tight text-[#131c2b]">GOAT</span>
            <span className="mt-[3px] block text-[8.5px] font-bold tracking-[0.22em] text-[#5c6b82]">HOOPS</span>
          </span>
        </Link>

        <div className="nav-strip flex w-full min-w-0 items-center gap-0.5 overflow-x-auto pr-2 sm:flex-1 lg:ml-2 xl:ml-4 xl:gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive = item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link key={item.href} href={item.href}
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
