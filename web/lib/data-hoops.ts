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
  validation: HoopsValidation; note: string;
};
export type HoopsTeamAgg = {
  abbr: string; name: string; g: number; w: number; l: number;
  pts: number; opp_pts: number; fgm: number; fga: number; tpm: number; tpa: number;
  ftm: number; fta: number; reb: number; ast: number; tov: number; stl: number;
  blk: number; paint: number | null; fastbreak: number | null;
};
export type HoopsTeamsDoc = { seasons: Record<string, HoopsTeamAgg[]> };
export type HoopsTeamGame = {
  id: string; date: string; type: string; opp: string | null; home: boolean;
  pts: number; opp_pts: number; res: string;
  /** balldontlie game id — no /games/{id} page exists for it */
  ext?: number;
};
export type HoopsTeamDoc = { seasons: Record<string, HoopsTeamAgg & { games: HoopsTeamGame[] }> };
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
    games: HoopsPlayerGame[];
  }>;
};
/** season roll-ups of balldontlie's v2-advanced game rows (advagg.json.gz) */
export type HoopsAdvAggPlayer = { gp: number; min: number | null } & Record<string, number | null>;
export type HoopsAdvAggLeague = Record<string, number | Record<string, number> | null>;
export type HoopsAdvAggDoc = {
  seasons: Record<string, Record<string, HoopsAdvAggPlayer>>;
  league: Record<string, HoopsAdvAggLeague>;
  lower_better: string[];
  note: string;
};
/** row = [season, age, gp, mpg, ppg, rpg, apg, ts_pct, usg_pct], seasons ascending */
export type HoopsCareersDoc = { players: Record<string, number[][]>; note: string };
export type HoopsStandRow = {
  abbr: string; conference: string | null; w: number; l: number; pct: number | null;
  conf_rank: number | null; home: [number, number] | null; road: [number, number] | null;
};
export type HoopsStandingsDoc = { seasons: Record<string, HoopsStandRow[]>; note: string };
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
} & { [k: string]: HoopsSSCat | HoopsSSCat[] | Record<string, number> | undefined };
export type HoopsSeasAvgsDoc = { season: number; players: Record<string, HoopsSSPlayer> };
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

/** Seasons the bake covers, newest first (falls back to nothing before the first bake). */
export async function hoopsSeasons(): Promise<number[]> {
  const meta = await getHoopsMeta();
  return Object.keys(meta?.seasons ?? {}).map(Number).sort((a, b) => b - a);
}
