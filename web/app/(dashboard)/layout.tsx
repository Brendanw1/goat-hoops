import { Nav } from "@/components/nav";
import { Ticker } from "@/components/ui/ticker";
import { RouteTracker } from "@/components/ui/back-link";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  /*
   * No session gate, same as the baseball sibling: a public site serving
   * public baked JSON has no mutation surface to guard. The baseball app's
   * grade-percentile providers and overlays are baseball-specific and stay
   * there; this shell is deliberately just nav + route tracking.
   */
  return (
    <div className="min-h-screen flex flex-col">
      <Nav />
      <Ticker />
      {/* filter-faithful back links: every pathname+search lands in a session stack */}
      <RouteTracker />
      <main className="flex-1 min-w-0 px-4 sm:px-6 pt-4 pb-10 max-w-[1440px] mx-auto w-full page-content">
        {children}
      </main>
    </div>
  );
}
