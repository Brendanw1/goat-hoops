"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { TeamDot } from "@/lib/team-dot";

/**
 * The rAF-driven marquee: a slow roll that EASES to a stop on hover (~0.55s
 * exponential) and back on leave — pure CSS can't decelerate
 * animation-play-state. Reduced-motion renders a static scrollable strip.
 */
export type TickerItem =
  | { kind: "injury"; status: string; player: string; team: string | null; comment: string }
  | { kind: "news"; headline: string; link: string | null };

const STATUS_CLS: Record<string, string> = {
  Out: "text-neg", "Out For Season": "text-neg", "Out Indefinitely": "text-neg",
  Doubtful: "text-neg", Suspended: "text-neg",
  "Day-To-Day": "text-flag", Questionable: "text-flag", GTD: "text-flag",
};

const BASE_PX_S = 30;  // slow roll
const TAU = 0.55;      // seconds of exponential easing toward the target speed

export function TickerTrack({ items }: { items: TickerItem[] }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const state = useRef({ x: 0, speed: BASE_PX_S, hover: false, last: 0, raf: 0 });
  const [still, setStill] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setStill(true);
      return;
    }
    const el = trackRef.current;
    if (!el) return;
    let half = 0;
    const measure = () => { half = el.scrollWidth / 2; };
    measure();
    window.addEventListener("resize", measure);

    const tick = (t: number) => {
      const s = state.current;
      const dt = Math.min((t - s.last) / 1000, 0.1);
      s.last = t;
      const target = s.hover ? 0 : BASE_PX_S;
      s.speed += (target - s.speed) * Math.min(1, dt / TAU);
      s.x -= s.speed * dt;
      if (half > 0 && -s.x >= half) s.x += half;
      el.style.transform = `translateX(${s.x.toFixed(1)}px)`;
      s.raf = requestAnimationFrame(tick);
    };
    state.current.raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(state.current.raf);
      window.removeEventListener("resize", measure);
    };
  }, [items]);

  const setHover = (v: boolean) => { state.current.hover = v; };

  const run = items.map((it, k) => {
    if (it.kind === "injury") {
      return (
        <span key={`i${k}`} className="inline-flex items-center gap-1.5 px-3 whitespace-nowrap">
          {it.team && <TeamDot abbr={it.team} size={14} />}
          <span className="text-text-secondary">{it.player}</span>
          <span className={`text-[10px] font-semibold ${STATUS_CLS[it.status] ?? "text-text-dim"}`}>
            {it.status}
          </span>
          {it.comment && <span className="text-text-dim/80">{it.comment}</span>}
          <span className="text-border-default">|</span>
        </span>
      );
    }
    return (
      <span key={`n${k}`} className="inline-flex items-center px-3 whitespace-nowrap">
        <Link href={it.link || "#"} target="_blank" rel="noopener noreferrer"
          className="text-text-secondary hover:text-text-primary hover:underline">
          {it.headline}
        </Link>
        <span className="text-border-default ml-3">|</span>
      </span>
    );
  });

  return (
    <div className="ticker relative overflow-hidden border-b border-border-subtle bg-surface-1 text-[11px] leading-6"
      title="injury report + headlines — hover to ease to a stop"
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      {still ? (
        <div className="flex py-1 overflow-x-auto">{run}</div>
      ) : (
        <div ref={trackRef} className="flex w-max py-1 will-change-transform">
          <div className="flex">{run}</div>
          <div className="flex" aria-hidden>{run}</div>
        </div>
      )}
      <div className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-gradient-to-r from-surface-0 to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-surface-0 to-transparent" />
    </div>
  );
}
