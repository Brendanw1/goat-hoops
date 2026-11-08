/**
 * The percentile judgment scale, one definition for every surface:
 *   ≥ .90  elite  (blue — --color-elite)
 *   ≥ .75  good   (green — text-pos)
 *   .25–.75 neutral
 *   <  .25 bad    (red — text-neg)
 * Identity colors (team/brand) and volume ramps stay out of this scale.
 */
export function pctTone(v: number | null | undefined): string {
  if (v == null) return "text-text-dim";
  if (v >= 0.9) return "text-elite font-medium";
  if (v >= 0.75) return "text-pos font-medium";
  if (v <= 0.25) return "text-neg font-medium";
  return "text-text-primary";
}

export function pctBarTone(v: number | null | undefined): string {
  if (v == null) return "bg-white/20";
  if (v >= 0.9) return "bg-elite/80";
  if (v >= 0.75) return "bg-pos/70";
  if (v <= 0.25) return "bg-neg/70";
  return "bg-white/30";
}
