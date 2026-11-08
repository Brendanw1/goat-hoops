import Link from "next/link";
import { teamColor } from "./team-colors";

function isDark(hex: string): boolean {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) < 140;
}

/** Team monogram: the identity logo treatment — a team-colored disc with the
 * abbreviation. Identity channel only; pairs with text via <TeamLink>. */
export function TeamDot({ abbr, size = 20 }: { abbr: string | null | undefined; size?: number }) {
  if (!abbr) return null;
  const c = teamColor(abbr) ?? "rgba(255,255,255,0.15)";
  const dark = isDark(c);
  return (
    <span aria-hidden
      className="rounded-full grid place-items-center shrink-0 font-black relative"
      style={{ background: `radial-gradient(circle at 32% 26%, ${c}f2, ${c} 58%, rgba(0,0,0,0.35))`,
               width: size, height: size,
               color: dark ? "rgba(255,255,255,0.94)" : "rgba(20,18,14,0.92)",
               fontSize: Math.max(size * 0.36, 7), letterSpacing: "-0.03em",
               boxShadow: `inset 0 0 0 ${Math.max(size * 0.045, 1)}px rgba(255,255,255,0.22), inset 0 0 0 ${Math.max(size * 0.09, 2)}px rgba(0,0,0,0.18)` }}>
      {abbr}
    </span>
  );
}

export function TeamLink({ abbr, name, size = 20 }: {
  abbr: string | null | undefined; name?: string | null; size?: number;
}) {
  if (!abbr) return null;
  return (
    <Link href={`/teams/${abbr}`} className="inline-flex items-center gap-1.5 group">
      <TeamDot abbr={abbr} size={size} />
      <span className="text-text-secondary group-hover:text-text-primary group-hover:underline">
        {name ?? abbr}
      </span>
    </Link>
  );
}
