"use client";

import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";

/**
 * The one deliberate client widget: a fuzzy player finder over the season's
 * board (~400-1900 names, passed as props — no extra fetch). Enter picks the
 * top hit; the site's other surfaces stay server-rendered.
 */
export function PlayerFinder({ players }: {
  players: { id: string; name: string; team: string | null }[];
}) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const hits = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (needle.length < 2) return [];
    return players
      .filter((p) => p.name.toLowerCase().includes(needle))
      .slice(0, 8);
  }, [q, players]);

  const go = (id: string) => {
    setQ("");
    setOpen(false);
    router.push(`/players/${id}`);
  };

  return (
    <div ref={boxRef} className="relative w-full max-w-sm"
      onBlur={(e) => { if (!boxRef.current?.contains(e.relatedTarget as Node)) setOpen(false); }}>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && hits[0]) go(hits[0].id);
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder="Find a player…"
        aria-label="Find a player"
        className="w-full rounded-lg border border-border-subtle bg-black/30 px-3 py-2 text-xs text-text-primary
          placeholder:text-text-dim/60 focus:outline-none focus:border-border-subtle focus:bg-black/50"
      />
      {open && hits.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-border-subtle bg-[#0b111c] shadow-xl overflow-hidden">
          {hits.map((p) => (
            <button key={p.id} type="button" onMouseDown={() => go(p.id)}
              className="flex w-full items-center justify-between px-3 py-1.5 text-xs text-text-primary hover:bg-white/[0.06] text-left">
              <span>{p.name}</span>
              <span className="text-text-dim">{p.team ?? "—"}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
