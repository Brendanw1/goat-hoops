import { getHoopsTicker } from "@/lib/data-hoops";
import { TickerTrack, type TickerItem } from "./ticker-track";

/**
 * The news/injury ticker — server shell that loads the baked ticker.json
 * (ESPN public APIs, fetched once per ingest run — the site never calls ESPN)
 * and hands items to the rAF-driven TickerTrack: a slow roll that EASES to a
 * stop on hover and back on leave. Status colors: Out red, DTD/Q violet.
 */
export async function Ticker() {
  const doc = await getHoopsTicker();
  if (!doc || (!doc.injuries.length && !doc.news.length)) return null;
  const items: TickerItem[] = [
    ...doc.injuries.map((i) => ({
      kind: "injury" as const, status: i.status, player: i.player,
      team: i.team, comment: i.comment,
    })),
    ...doc.news.map((n) => ({
      kind: "news" as const, headline: n.headline, link: n.link,
    })),
  ];
  return <TickerTrack items={items} />;
}
