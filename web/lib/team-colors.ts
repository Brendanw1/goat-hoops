/**
 * Team identity colors — the bright/visible face of each franchise's palette,
 * chosen for legibility on the dark surface. IDENTITY only: these never
 * encode judgment (pos/neg/flag own that), they mark who is who.
 * Keys follow the site's abbr convention (GS/NO/NY/SA/UTAH/WSH).
 */
export const TEAM_COLORS: Record<string, string> = {
  ATL: "#E03A3E", BOS: "#00843D", BKN: "#A7A9AC", CHA: "#00788C",
  CHI: "#CE1141", CLE: "#FDBB30", DAL: "#0064CE", DEN: "#FEC524",
  DET: "#ED4E43", GS: "#FFC72C", HOU: "#CE1141", IND: "#FDBB30",
  LAC: "#ED4E43", LAL: "#FDB927", MEM: "#6189B9", MIA: "#F9A01B",
  MIL: "#EEE1C6", MIN: "#78BE20", NO: "#C8102E", NY: "#F58426",
  OKC: "#007AC1", ORL: "#7BAFD4", PHI: "#006BB6", PHX: "#E56020",
  POR: "#E03A3E", SAC: "#7A4FA0", SA: "#C4CED4", TOR: "#CE1141",
  UTAH: "#F9A01B", WSH: "#E31837",
};

export function teamColor(abbr: string | null | undefined): string | undefined {
  return abbr ? TEAM_COLORS[abbr.toUpperCase()] : undefined;
}
