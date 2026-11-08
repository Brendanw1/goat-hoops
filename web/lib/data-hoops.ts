/**
 * Server-side fetchers for the basketball surfaces (hoops/... keys on R2).
 * Descriptive Phase 1 only — every number is a raw mart value or a plain
 * average/per-36; see pipeline/hoops_export.py for the bake and the LUMA
 * validation gate recorded in hoops/meta.json.
 */
import { cache } from "react";
import { fetchFromR2, fetchGzippedJson } from "./r2";

export type HoopsGameRow = {
  id: string; date: string; season: number; type: string;
  away: string | null; home: string | null;
  away_score: number; home_score: number; ot: number | null;
  /** balldontlie game id — no /games/{id} report exists for it */
  ext?: number;
};
export type HoopsGamesDoc = { season: number; label: string; games: HoopsGameRow[] };
export type HoopsValidation = {
  gate: string; games_2024_25: string; games_2026_27: string; boxes: number;
  credit: string; boxes_ast_note: string;
};
export type HoopsMeta = {
  seasons: Record<string, { games: number; first: string; last: string; source?: "espn" | "bdl" }>;
  validation: HoopsValidation;
  starters?: Record<string, {
    coverage: number; game_teams: number; exact5: number; gs_merged: boolean;
  }>;
  note: string;
};
export type HoopsTeamAgg = {
  abbr: string; name: string; g: number; w: number; l: number;
  pts: number; opp_pts: number; fgm: number; fga: number; tpm: number; tpa: number;
  ftm: number; fta: number; reb: number; ast: number; tov: number; stl: number;
  blk: number; paint: number | null; fastbreak: number | null;
};
/** §0d-gated pace / four-factors / ratings block (RESULTS-HOOPS §0d) */
export type HoopsTeamAnalytics = {
  pace: number; poss_g: number;
  ortg: number | null; drtg: number | null; net: number | null;
  efg: number; tsp: number; fg3ar: number; ftr: number;
  tov_pct: number; orb_pct: number; drb_pct: number;
  opp_efg: number; opp_tsp: number; opp_tov_pct: number; opp_orb_pct: number;
  partial: boolean; src: "bdl" | "espn";
};
export type HoopsTeamsDoc = {
  seasons: Record<string, HoopsTeamAgg[]>;
  /** per-season league env for the team analytics context coloring */
  league?: Record<string, HoopsTeamAnalytics>;
};
export type HoopsTeamGame = {
  id: string; date: string; type: string; opp: string | null; home: boolean;
  pts: number; opp_pts: number; res: string;
  /** balldontlie game id — no /games/{id} page exists for it */
  ext?: number;
};
export type HoopsTeamDoc = {
  seasons: Record<string, HoopsTeamAgg & {
    games: HoopsTeamGame[];
    /** most-used starting fives (exact-5 groups only; pulls are partial — coverage in meta) */
    starters5?: { names: string[]; g: number }[];
    analytics?: HoopsTeamAnalytics;
  }>;
};
export type HoopsPlayerRow = {
  id: string; name: string; pos: string | null; team: string | null;
  gp: number; gs: number | null; min: number; pts: number; reb: number; ast: number;
  stl: number; blk: number; tov: number; pts36: number | null; reb36: number | null; ast36: number | null;
  oreb?: number | null; dreb?: number | null;
  fgp?: number | null; tpp?: number | null; ftp?: number | null;
  src?: "espn" | "bdl";
};
export type HoopsPlayersDoc = { seasons: Record<string, HoopsPlayerRow[]> };
export type HoopsPlayerGame = {
  id: string; date: string; opp: string | null; home: boolean; res: string;
  min: number | null; pts: number; reb: number; ast: number; stl: number; blk: number;
  tov: number; pf: number; pm: number | null; fg: string | null; tp: string | null; ft: string | null;
  /** balldontlie game id — the site's /games/{id} pages are ESPN ids only */
  ext?: number;
};
export type HoopsPlayerDoc = {
  id: string; name: string;
  seasons: Record<string, {
    team: string | null; gp: number; gs: number | null;
    totals: { min: number; pts: number; reb: number; ast: number; stl: number; blk: number; tov: number };
    per_game: { min: number; pts: number; reb: number; ast: number; stl: number; blk: number; tov: number };
    per36: { pts: number | null; reb: number | null; ast: number | null };
    shoot?: { fg: [number, number]; tp: [number, number]; ft: [number, number];
             oreb: number | null; dreb: number | null };
    /** METRICS.md splits from the game-log grain (context cuts, neutral) */
    splits?: Record<string, Record<string, { g: number } & Record<string, number>>>;
    games: HoopsPlayerGame[];
  }>;
};
/** season roll-ups of balldontlie's v2-advanced game rows (advagg.json.gz) */
export type HoopsAdvAggPlayer = { gp: number } & Record<string, number | null>;
export type HoopsAdvAggLeague = Record<string, number | Record<string, number> | null>;
export type HoopsAdvAggDoc = {
  seasons: Record<string, { players: Record<string, HoopsAdvAggPlayer> }>;
  league: Record<string, HoopsAdvAggLeague>;
  lower_better: string[];
  /** per site season: distinct games with advanced rows vs the games spine */
  coverage?: Record<string, { games: number; spine?: number; full?: boolean }>;
  note: string;
};
/** row = [season, age, gp, mpg, ppg, rpg, apg, ts_pct, usg_pct], seasons ascending */
export type HoopsCareersDoc = { players: Record<string, number[][]>; note: string };
export type HoopsStandRow = {
  abbr: string; conference: string | null; w: number; l: number; pct: number | null;
  conf_rank: number | null; home: [number, number] | null; road: [number, number] | null;
};
export type HoopsStandingsDoc = { seasons: Record<string, HoopsStandRow[]>; note: string };

/** exploration-layer docs (pipeline/explore.py) — descriptive, not forecasts */
export type HoopsSimilarDoc = {
  season: number; k: number; fields: string[];
  archetypes: Record<string, { label: string; size: number; centroid: [string, number][] }>;
  players: Record<string, { a: number; n: [string, number][] }>;
  note: string;
};
export type HoopsSurplusPlayer = {
  prod_z: number; prod_pct: number;
  sal: number | null; sal_pct: number | null; surplus: number | null;
};
export type HoopsSurplusDoc = {
  season_prod: number; season_salary: number; fields: string[];
  players: Record<string, HoopsSurplusPlayer>; note: string;
};
export type HoopsClutchDoc = {
  seasons: Record<string, Record<string, {
    gp: number | null; ts_d: number | null; usg_d: number | null;
    net_d: number | null; pie_d: number | null;
  }>>;
  note: string;
};
export type HoopsReboundDoc = {
  seasons: Record<string, {
    players: Record<string, { reb36: number; reb_ch: number; conv: number }>;
    dist: Record<string, number>;
  }>;
  note: string;
};
export type HoopsContractDeal = {
  type: string | null; status: string | null;
  start: number | null; end: number | null; years: number | null;
  total_value: number | null; avg_salary: number | null;
  guaranteed: number | null; guaranteed_signing: number | null;
  signed_using: string | null; fa_year: number | null; fa_status: string | null;
  notes: string | null; team: string | null;
};
export type HoopsContractDoc = {
  deals: Record<string, HoopsContractDeal[]>;
  salaries: Record<string, {
    season: number | null; cap_hit: number | null; base_salary: number | null; team: string | null;
  }>;
  unmapped: number; note: string;
};
export type HoopsBoxRow = {
  name: string; pos: string | null; starter: boolean; dnp: boolean;
  min: number | null; pts: number | null; reb: number | null; ast: number | null;
  stl: number | null; blk: number | null; tov: number | null; pf: number | null;
  pm: number | null; fg: string | null; tp: string | null; ft: string | null;
};
export type HoopsShot = {
  p: number; t: number | null; x: number | null; y: number | null;
  m: boolean; v: number; pa: number | null; a: string | null; s: string | null; ty: string | null;
};
export type HoopsPlay = {
  p: number; t: number | null; ty: string | null; tx: string | null;
  a: string | null; hs: number; as: number;
};
export type HoopsGameDoc = {
  game: HoopsGameRow;
  teams: { abbr: string | null; side: string; points: number;
           paint: number | null; fastbreak: number | null; reb: number | null;
           ast: number | null; tov: number | null }[];
  boxes: Record<string, HoopsBoxRow[]>;
  shots: HoopsShot[];
  plays: HoopsPlay[];
};

export type HoopsRead = {
  n: string; title: string; date: string;
  verdict: "PASS" | "FAIL" | "TIE" | null; line: string | null;
  benchmark: number | null; why: string | null;
};
export type HoopsReadsDoc = {
  sections: HoopsRead[];
  gates: { n: string; title: string; verdict: string; line: string; why: string }[];
  ladder: [string, number][];
  note: string;
};
export type HoopsMethodsDoc = {
  intro: string; sections: { title: string; body: string }[]; note: string;
};

export const getHoopsMeta = cache(async (): Promise<HoopsMeta | null> =>
  (await fetchFromR2<HoopsMeta>("meta.json").catch(() => null)) ?? null);

export const getHoopsGames = cache(async (season: number): Promise<HoopsGamesDoc | null> =>
  (await fetchFromR2<HoopsGamesDoc>(`games_${season}.json`).catch(() => null)) ?? null);

export const getHoopsGame = cache(async (gid: string): Promise<HoopsGameDoc | null> =>
  (await fetchGzippedJson<HoopsGameDoc>(`game/${gid}.json.gz`)) ?? null);

export const getHoopsTeams = cache(async (): Promise<HoopsTeamsDoc | null> =>
  (await fetchFromR2<HoopsTeamsDoc>("teams.json").catch(() => null)) ?? null);

export const getHoopsTeam = cache(async (abbr: string): Promise<HoopsTeamDoc | null> =>
  (await fetchGzippedJson<HoopsTeamDoc>(`team/${abbr.toLowerCase()}.json.gz`)) ?? null);

export const getHoopsPlayers = cache(async (): Promise<HoopsPlayersDoc | null> =>
  (await fetchFromR2<HoopsPlayersDoc>("players.json").catch(() => null)) ?? null);

export const getHoopsPlayer = cache(async (id: string): Promise<HoopsPlayerDoc | null> =>
  (await fetchGzippedJson<HoopsPlayerDoc>(`player/${id}.json.gz`)) ?? null);

export type HoopsSSCat = Record<string, number | string | null>;
export type HoopsSSPlayer = {
  playtype?: HoopsSSCat[];
  zones?: Record<string, HoopsSSCat>;
  bands?: Record<string, HoopsSSCat>;
  pct_ranks?: Record<string, number>;
  // the flat category blocks the bake writes (hoops_export.py category map)
  adv?: HoopsSSCat; clutch?: HoopsSSCat; defense?: HoopsSSCat; hustle?: HoopsSSCat;
  speed?: HoopsSSCat; drives?: HoopsSSCat; passing?: HoopsSSCat; paint?: HoopsSSCat;
  catch_shoot?: HoopsSSCat; pullup?: HoopsSSCat; post?: HoopsSSCat; elbow?: HoopsSSCat;
  eff?: HoopsSSCat; poss_t?: HoopsSSCat; def_t?: HoopsSSCat;
  /** §9 zone shot-making benchmark (bake-time, gate-gated) */
  shootmk?: { xefg: number; efg: number; diff: number; n_fga: number };
  /** position letter (G/F/C, first of the feed's value) + its pool's ranks */
  pos?: string;
  pct_ranks_pos?: Record<string, number>;
} & { [k: string]: HoopsSSCat | HoopsSSCat[] | Record<string, number> | undefined };
export type HoopsSeasAvgsDoc = {
  season: number;
  players: Record<string, HoopsSSPlayer>;
  /** §9: league zone FG% (fga-weighted, same-season pool; efgp values 3s ×1.5) */
  leagueZones?: Record<string, { fga: number; fgp: number; efgp: number }> | null;
};
export type HoopsShotGrid = { n: number; fgm: number; cells: [number, number, number, number][] };
export type HoopsPlayerShotsDoc = { season: number; binsize: number; players: Record<string, HoopsShotGrid> };

export const getHoopsSeasAvgs = cache(async (season: number): Promise<HoopsSeasAvgsDoc | null> =>
  (await fetchGzippedJson<HoopsSeasAvgsDoc>(`seasavgs_${season}.json.gz`)) ?? null);

export const getHoopsPlayerShots = cache(async (season: number): Promise<HoopsPlayerShotsDoc | null> =>
  (await fetchGzippedJson<HoopsPlayerShotsDoc>(`playershots_${season}.json.gz`)) ?? null);

export const getHoopsContracts = cache(async (): Promise<HoopsContractDoc | null> =>
  (await fetchFromR2<HoopsContractDoc>("contracts.json").catch(() => null)) ?? null);

export const getHoopsAdvAgg = cache(async (): Promise<HoopsAdvAggDoc | null> =>
  (await fetchGzippedJson<HoopsAdvAggDoc>("advagg.json.gz").catch(() => null)) ?? null);

export const getHoopsCareers = cache(async (): Promise<HoopsCareersDoc | null> =>
  (await fetchGzippedJson<HoopsCareersDoc>("careers.json.gz").catch(() => null)) ?? null);

export const getHoopsStandings = cache(async (): Promise<HoopsStandingsDoc | null> =>
  (await fetchFromR2<HoopsStandingsDoc>("standings.json").catch(() => null)) ?? null);

export const getHoopsSimilar = cache(async (): Promise<HoopsSimilarDoc | null> =>
  (await fetchGzippedJson<HoopsSimilarDoc>("similar.json.gz").catch(() => null)) ?? null);

export const getHoopsSurplus = cache(async (): Promise<HoopsSurplusDoc | null> =>
  (await fetchGzippedJson<HoopsSurplusDoc>("surplus.json.gz").catch(() => null)) ?? null);

export const getHoopsClutch = cache(async (): Promise<HoopsClutchDoc | null> =>
  (await fetchGzippedJson<HoopsClutchDoc>("clutch.json.gz").catch(() => null)) ?? null);

export const getHoopsReads = cache(async (): Promise<HoopsReadsDoc | null> =>
  (await fetchGzippedJson<HoopsReadsDoc>("reads.json.gz").catch(() => null)) ?? null);
export const getHoopsMethods = cache(async (): Promise<HoopsMethodsDoc | null> =>
  (await fetchGzippedJson<HoopsMethodsDoc>("methods.json.gz").catch(() => null)) ?? null);
export const getHoopsRebound = cache(async (): Promise<HoopsReboundDoc | null> =>
  (await fetchGzippedJson<HoopsReboundDoc>("rebound.json.gz").catch(() => null)) ?? null);

/** Seasons the bake covers, newest first (falls back to nothing before the first bake). */
export async function hoopsSeasons(): Promise<number[]> {
  const meta = await getHoopsMeta();
  return Object.keys(meta?.seasons ?? {}).map(Number).sort((a, b) => b - a);
}
