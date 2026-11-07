import Link from "next/link";
import { Container } from "@/components/Container";
import { constructMetadata } from "@/lib/seo";
import { ArrowUpRight, TrendingUp, Clock, Globe } from "lucide-react";

export const metadata = constructMetadata({
  title: "Front Page — Leading US & Global News Discovery",
  description: "Real-time automated news indexing, verified source tracking, and broadsheet editorial discovery.",
});

export default function HomePage() {
  return (
    <div className="space-y-8 py-6">
      {/* Top Editorial Lead Section */}
      <Container>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 border-b border-border pb-8">
          {/* Main Lead Feature (8 cols) */}
          <section className="lg:col-span-8 flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-center space-x-2 mb-2">
                <span className="text-[11px] font-bold uppercase tracking-widest text-secondary">
                  Top Story • Wire Discovery
                </span>
                <span className="text-border">|</span>
                <span className="text-xs text-muted flex items-center space-x-1">
                  <Clock className="w-3 h-3" />
                  <span>Real-time ingestion active</span>
                </span>
              </div>

              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-serif font-bold text-foreground leading-tight">
                MetroScope Automated News Discovery Engine
              </h1>

              <p className="mt-4 text-base sm:text-lg text-muted leading-relaxed font-sans">
                A modern broadsheet news platform powered by the GDELT DOC 2.0 API. Aggregating, normalizing, and delivering unbiased news intelligence across global publishing sources.
              </p>
            </div>

            {/* Architecture Highlights Card */}
            <div className="border border-border bg-surface-lowest p-6 rounded-lg space-y-4">
              <h2 className="text-sm font-bold uppercase tracking-wider text-secondary flex items-center space-x-2">
                <TrendingUp className="w-4 h-4" />
                <span>Phase 1 Platform Foundation</span>
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div className="border-l-2 border-secondary pl-3 space-y-1">
                  <span className="font-semibold text-foreground">Discovery Engine</span>
                  <p className="text-muted">Python-based asynchronous GDELT DOC 2.0 integration with retry backoff.</p>
                </div>
                <div className="border-l-2 border-secondary pl-3 space-y-1">
                  <span className="font-semibold text-foreground">Storage Layer</span>
                  <p className="text-muted">PostgreSQL persistence with SQLAlchemy 2.0 and versioned Alembic migrations.</p>
                </div>
                <div className="border-l-2 border-secondary pl-3 space-y-1">
                  <span className="font-semibold text-foreground">Frontend Delivery</span>
                  <p className="text-muted">Next.js App Router, Tailwind CSS, Playfair Display typography, and dark mode.</p>
                </div>
              </div>
            </div>
          </section>

          {/* Wire Feed Sidebar (4 cols) */}
          <aside className="lg:col-span-4 border-t lg:border-t-0 lg:border-l border-border lg:pl-8 space-y-6">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <h2 className="text-xs font-bold uppercase tracking-widest text-foreground flex items-center space-x-2">
                <Globe className="w-3.5 h-3.5 text-secondary" />
                <span>Live Wire Feed</span>
              </h2>
              <span className="text-[10px] uppercase tracking-wider text-secondary font-semibold">
                Auto-Updating
              </span>
            </div>

            <div className="space-y-4 text-xs divide-y divide-border">
              <div className="pt-3 first:pt-0 space-y-1">
                <span className="text-[10px] font-bold text-secondary uppercase tracking-wider">
                  Technology Desk
                </span>
                <Link
                  href="/category/technology"
                  className="font-serif font-semibold text-sm text-foreground hover:text-secondary block transition-colors"
                >
                  Global Semiconductor Supply Chains Pivot Toward Automated Fabrication Hubs
                </Link>
                <span className="text-muted text-[11px] block">Discovered via GDELT Index • 12 mins ago</span>
              </div>

              <div className="pt-3 space-y-1">
                <span className="text-[10px] font-bold text-secondary uppercase tracking-wider">
                  Business & Markets
                </span>
                <Link
                  href="/category/markets"
                  className="font-serif font-semibold text-sm text-foreground hover:text-secondary block transition-colors"
                >
                  Federal Reserve Signals Measured Monetary Adjustments Amid Treasury Yield Shifts
                </Link>
                <span className="text-muted text-[11px] block">Discovered via GDELT Index • 28 mins ago</span>
              </div>

              <div className="pt-3 space-y-1">
                <span className="text-[10px] font-bold text-secondary uppercase tracking-wider">
                  World Affairs
                </span>
                <Link
                  href="/category/world"
                  className="font-serif font-semibold text-sm text-foreground hover:text-secondary block transition-colors"
                >
                  Transatlantic Energy Infrastructure Summit Concludes with Grid Modernization Compact
                </Link>
                <span className="text-muted text-[11px] block">Discovered via GDELT Index • 44 mins ago</span>
              </div>
            </div>

            <Link
              href="/category/us-news"
              className="inline-flex items-center justify-between w-full p-2.5 rounded bg-surface-container hover:bg-surface-high transition-colors text-xs font-semibold text-foreground"
            >
              <span>Explore All Wire Dispatches</span>
              <ArrowUpRight className="w-4 h-4 text-secondary" />
            </Link>
          </aside>
        </div>
      </Container>

      {/* Featured Desks Section */}
      <Container>
        <div className="space-y-6">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <h2 className="text-xl font-serif font-bold text-foreground">
              Editorial Coverage Desks
            </h2>
            <Link
              href="/search"
              className="text-xs uppercase font-bold tracking-wider text-secondary hover:underline"
            >
              Search Coverage Archive →
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                title: "US News & Politics",
                slug: "us-news",
                desc: "Federal policy analysis, congressional legislation tracking, and nationwide civic reporting.",
              },
              {
                title: "Global Technology & AI",
                slug: "technology",
                desc: "Autonomous systems, enterprise computing, frontier models, and cybersecurity intelligence.",
              },
              {
                title: "Economics & Markets",
                slug: "business",
                desc: "Capital market indicators, global macroeconomic trends, inflation indices, and industry reports.",
              },
            ].map((desk) => (
              <div
                key={desk.slug}
                className="border border-border bg-surface-lowest p-5 rounded-lg space-y-3 hover:border-secondary transition-colors"
              >
                <span className="text-[11px] font-bold uppercase tracking-wider text-secondary">
                  News Desk
                </span>
                <h3 className="text-lg font-serif font-bold text-foreground">
                  <Link href={`/category/${desk.slug}`} className="hover:text-secondary transition-colors">
                    {desk.title}
                  </Link>
                </h3>
                <p className="text-xs text-muted leading-relaxed">{desk.desc}</p>
                <Link
                  href={`/category/${desk.slug}`}
                  className="inline-flex items-center space-x-1 text-xs font-semibold uppercase tracking-wider text-secondary hover:underline pt-2"
                >
                  <span>View Desk Coverage</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </Container>
    </div>
  );
}
