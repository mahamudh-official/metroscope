import Link from "next/link";
import Image from "next/image";
import { Container } from "@/components/Container";
import { constructMetadata } from "@/lib/seo";
import {
  Clock,
  TrendingUp,
  ArrowUpRight,
  ShieldCheck,
  Search,
  Radio,
  Newspaper,
  Compass,
} from "lucide-react";
import { fetchArticles, ArticleListItem } from "@/lib/api";
import { resolveArticleAttribution } from "@/lib/attribution";

export const metadata = constructMetadata({
  title: "National & International News",
  description:
    "Curated headlines, permitted summaries, and direct attribution to original reporting across US and world newsrooms.",
  canonicalUrl: "/",
});

export const revalidate = 60;

function formatTimestamp(isoString?: string | null): string {
  if (!isoString) return "Latest Edition";
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60 && diffMin >= 0) return `${Math.max(1, diffMin)}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24 && diffHours >= 0) return `${diffHours}h ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "Recently Published";
  }
}

const EDITORIAL_DESKS = [
  {
    title: "US News",
    slug: "us",
    desc: "National affairs, federal policy, and nationwide civic reporting.",
  },
  {
    title: "World News",
    slug: "world",
    desc: "International diplomacy, geopolitical developments, and global events.",
  },
  {
    title: "Politics",
    slug: "politics",
    desc: "Legislative tracking, election coverage, and governance analysis.",
  },
  {
    title: "Business & Markets",
    slug: "business",
    desc: "Capital markets, corporate finance, trade policy, and macroeconomic trends.",
  },
  {
    title: "Technology & AI",
    slug: "technology",
    desc: "Enterprise computing, frontier AI research, semiconductor industry, and cybersecurity.",
  },
  {
    title: "Science & Space",
    slug: "science",
    desc: "Space exploration, astrophysics, biological discoveries, and scientific breakthroughs.",
  },
  {
    title: "Health & Medicine",
    slug: "health",
    desc: "Public health initiatives, clinical research, medical advancements, and wellness.",
  },
  {
    title: "Environment & Climate",
    slug: "environment",
    desc: "Climate science, renewable energy transitions, conservation, and policy.",
  },
  {
    title: "Sports",
    slug: "sports",
    desc: "Championship reporting, athletic analysis, league developments, and major events.",
  },
  {
    title: "Culture & Entertainment",
    slug: "entertainment",
    desc: "Arts, film, media, literature, and cultural commentary.",
  },
];

export default async function HomePage() {
  const articlesData = await fetchArticles({ page: 1, pageSize: 24 });
  const articles: ArticleListItem[] = articlesData.items || [];

  // When database has zero published articles, render a professional newsroom dispatch
  // rather than synthetic or fallback placeholder articles
  if (articles.length === 0) {
    return (
      <div className="space-y-12 py-8">
        <Container>
          {/* Masthead Newsroom Dispatch */}
          <div className="bg-surface-lowest rounded-2xl border border-border p-8 sm:p-12 shadow-sm space-y-8">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-6">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-secondary animate-pulse" />
                <span className="text-xs font-bold uppercase tracking-widest text-secondary">
                  Newsroom Dispatch • Daily Edition
                </span>
              </div>
              <span className="text-xs text-muted flex items-center gap-1.5 font-medium">
                <Clock className="w-3.5 h-3.5" />
                Updated Continuous Broadcast
              </span>
            </div>

            <div className="max-w-3xl space-y-4">
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-serif font-bold text-foreground leading-tight tracking-tight">
                Today&apos;s Curated Edition Is Being Prepared
              </h1>
              <p className="text-base sm:text-lg text-muted font-sans leading-relaxed">
                The MetroScope newsroom continuously ingests, fact-checks, and validates reporting from verified national and international news providers. Certified dispatches appear here immediately upon passing editorial relevance, rights authorization, and hero image verification cycles.
              </p>
            </div>

            {/* Operational Quality Badges */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div className="p-4 rounded-xl bg-surface-low border border-border/80 flex items-start gap-3">
                <ShieldCheck className="w-5 h-5 text-secondary shrink-0 mt-0.5" />
                <div>
                  <span className="text-xs font-bold text-foreground block">
                    Strict Editorial Gate
                  </span>
                  <span className="text-[11px] text-muted">
                    10-category canonical schema &amp; verified republication rights
                  </span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-surface-low border border-border/80 flex items-start gap-3">
                <Clock className="w-5 h-5 text-secondary shrink-0 mt-0.5" />
                <div>
                  <span className="text-xs font-bold text-foreground block">
                    Scheduled Ingestion
                  </span>
                  <span className="text-[11px] text-muted">
                    08:00 Morning &amp; 20:00 Evening (Asia/Dhaka)
                  </span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-surface-low border border-border/80 flex items-start gap-3">
                <Radio className="w-5 h-5 text-secondary shrink-0 mt-0.5" />
                <div>
                  <span className="text-xs font-bold text-foreground block">
                    Direct Wire Provider
                  </span>
                  <span className="text-[11px] text-muted">
                    Webz.io API with automated budget protection
                  </span>
                </div>
              </div>
            </div>

            {/* Search Coverage Archive */}
            <div className="pt-4 border-t border-border">
              <form action="/search" method="GET" className="max-w-xl flex gap-2">
                <div className="relative flex-1">
                  <input
                    type="text"
                    name="q"
                    placeholder="Search across headlines, topics, and archives..."
                    className="w-full pl-10 pr-4 py-2.5 text-xs sm:text-sm rounded-lg border border-border bg-surface text-foreground placeholder:text-muted focus:outline-none focus:border-secondary transition-colors"
                  />
                  <Search className="w-4 h-4 text-muted absolute left-3.5 top-3 pointer-events-none" />
                </div>
                <button
                  type="submit"
                  className="px-5 py-2.5 text-xs font-bold uppercase tracking-wider rounded-lg bg-secondary text-white hover:bg-secondary/90 transition-colors shrink-0"
                >
                  Search
                </button>
              </form>
            </div>
          </div>
        </Container>

        {/* SECTION 2: EDITORIAL COVERAGE DESKS */}
        <Container>
          <section className="space-y-6">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <span className="text-[11px] font-bold text-secondary uppercase tracking-widest block">
                  Editorial Structure
                </span>
                <h2 className="text-2xl font-serif font-bold text-foreground">
                  Explore Coverage Desks
                </h2>
              </div>
              <Link
                href="/search"
                className="text-xs uppercase font-bold tracking-wider text-secondary hover:underline flex items-center gap-1"
              >
                <span>Search Archive</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              {EDITORIAL_DESKS.map((desk) => (
                <Link
                  key={desk.slug}
                  href={`/category/${desk.slug}`}
                  className="group p-4 bg-surface-lowest border border-border rounded-xl hover:border-secondary hover:shadow-sm transition-all flex flex-col justify-between"
                >
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-secondary block mb-1">
                      Desk
                    </span>
                    <h3 className="font-serif font-bold text-base text-foreground group-hover:text-secondary transition-colors mb-2">
                      {desk.title}
                    </h3>
                    <p className="text-xs text-muted leading-relaxed line-clamp-3">
                      {desk.desc}
                    </p>
                  </div>
                  <div className="pt-3 border-t border-border/60 mt-4 flex items-center justify-between text-[11px] font-semibold text-secondary">
                    <span>Browse Desk</span>
                    <ArrowUpRight className="w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                  </div>
                </Link>
              ))}
            </div>
          </section>
        </Container>
      </div>
    );
  }

  // When published articles exist, render the full Stitch editorial hierarchy
  const leadArticle = articles[0];
  const leadAttribution = resolveArticleAttribution(
    leadArticle.author,
    leadArticle.publisher_name,
    leadArticle.source?.name,
    leadArticle.source?.domain,
    leadArticle.title
  );

  const railArticles = articles.length > 1 ? articles.slice(1, 4) : [];
  const investigationArticles = articles.length > 4 ? articles.slice(4, 8) : [];
  const secondaryArticles = articles.length > 8 ? articles.slice(8, 12) : [];
  const mostReadArticles = articles.slice(0, 5);

  return (
    <div className="space-y-12 py-6">
      {/* SECTION 1: LEAD EDITORIAL PACKAGE (8 Cols Lead + 4 Cols Rail) */}
      <Container>
        <section className="border-b border-border pb-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Primary Lead Story (8 Cols) */}
            <article className="lg:col-span-8 flex flex-col group bg-surface-lowest p-6 rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow">
              {/* Category & Time Eyebrow */}
              <div className="flex items-center gap-2 mb-3 text-xs">
                <span className="font-bold text-secondary uppercase tracking-widest text-[11px]">
                  {leadArticle.category?.name || "Lead Story"}
                </span>
                <span className="text-border">•</span>
                <span className="text-muted flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-muted" />
                  {formatTimestamp(leadArticle.published_at)}
                </span>
                <span className="text-border">•</span>
                <span className="text-muted">Verified Coverage</span>
              </div>

              {/* Headline */}
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-serif font-bold text-foreground group-hover:text-secondary transition-colors mb-4 leading-tight">
                <Link href={`/article/${leadArticle.slug}`}>
                  {leadArticle.title}
                </Link>
              </h1>

              {/* 16:9 Hero Image (when genuine image is available) */}
              {leadArticle.image_url && (
                <div className="relative w-full aspect-[16/9] mb-5 overflow-hidden rounded-lg bg-surface-container border border-border">
                  <Image
                    src={leadArticle.image_url}
                    alt={leadArticle.title}
                    fill
                    priority
                    unoptimized
                    referrerPolicy="no-referrer"
                    className="object-cover group-hover:scale-102 transition-transform duration-500"
                  />
                  <div className="absolute bottom-2 right-2 bg-primary/85 backdrop-blur-sm text-white px-2 py-0.5 rounded text-[10px] font-sans">
                    Photo via {leadAttribution.sourceName}
                  </div>
                </div>
              )}

              {/* Summary */}
              {leadArticle.description && (
                <p className="text-base sm:text-lg text-muted mb-6 leading-relaxed font-sans">
                  {leadArticle.description}
                </p>
              )}

              {/* Byline & Attribution Bar */}
              <div className="flex items-center justify-between pt-4 border-t border-border mt-auto">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center font-bold text-primary text-xs">
                    {leadAttribution.avatarInitials}
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-foreground block">
                      {leadAttribution.byline}
                    </span>
                    <span className="text-[11px] text-muted">
                      Reporting from {leadAttribution.sourceName}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-muted">
                  <Link
                    href={`/article/${leadArticle.slug}`}
                    className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-secondary hover:underline px-2 py-1"
                  >
                    <span>Read Story</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            </article>

            {/* Side Editorial Rail: Essential Analysis (4 Cols) */}
            <aside className="lg:col-span-4 flex flex-col gap-4">
              <div className="bg-surface-low border border-border px-4 py-2.5 rounded-lg flex items-center justify-between">
                <h2 className="text-xs uppercase text-foreground font-bold tracking-wider flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-secondary" />
                  Essential Analysis
                </h2>
                <span className="text-[11px] text-muted">Curated by Editors</span>
              </div>

              {railArticles.length > 0 ? (
                railArticles.map((art) => {
                  const artAttr = resolveArticleAttribution(
                    art.author,
                    art.publisher_name,
                    art.source?.name,
                    art.source?.domain,
                    art.title
                  );
                  return (
                    <article
                      key={art.id}
                      className="bg-surface-lowest p-5 rounded-lg border border-border shadow-sm group cursor-pointer hover:shadow-md transition-shadow flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-[10px] font-bold text-secondary uppercase tracking-wider">
                            {art.category?.name || "Dispatch"}
                          </span>
                          <span className="text-border text-xs">•</span>
                          <span className="text-[11px] text-muted">
                            {formatTimestamp(art.published_at)}
                          </span>
                        </div>
                        <h3 className="font-serif font-semibold text-base text-foreground group-hover:text-secondary transition-colors leading-snug mb-2">
                          <Link href={`/article/${art.slug}`}>
                            {art.title}
                          </Link>
                        </h3>
                        {art.description && (
                          <p className="text-xs text-muted line-clamp-2 mb-3 leading-relaxed">
                            {art.description}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-muted pt-2 border-t border-border/50">
                        <span>{artAttr.byline}</span>
                        <span className="font-medium text-secondary">{artAttr.sourceName}</span>
                      </div>
                    </article>
                  );
                })
              ) : (
                <div className="p-6 text-center text-xs text-muted border border-border rounded-lg bg-surface-lowest">
                  Additional curated analysis will appear here as stories develop.
                </div>
              )}
            </aside>
          </div>
        </section>
      </Container>

      {/* SECTION 2: TOP NATIONAL INVESTIGATIONS (4-Column Bento Feature) */}
      {investigationArticles.length > 0 && (
        <Container>
          <section className="border-b border-border pb-10">
            <div className="flex items-center justify-between pb-3 mb-6 border-b border-border">
              <div>
                <span className="text-[11px] font-bold text-secondary uppercase tracking-widest block">
                  In-Depth Reporting
                </span>
                <h2 className="text-xl sm:text-2xl font-serif font-bold text-foreground">
                  Top National Investigations
                </h2>
              </div>
              <span className="text-xs text-muted">Updated continuously</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {investigationArticles.map((art) => {
                const artAttr = resolveArticleAttribution(
                  art.author,
                  art.publisher_name,
                  art.source?.name,
                  art.source?.domain,
                  art.title
                );
                return (
                  <article
                    key={art.id}
                    className="bg-surface-lowest rounded-lg p-4 border border-border flex flex-col shadow-sm group hover:shadow-md transition-shadow"
                  >
                    {art.image_url ? (
                      <div className="relative aspect-[4/3] rounded-lg overflow-hidden mb-3 bg-surface-container border border-border">
                        <Image
                          src={art.image_url}
                          alt={art.title}
                          fill
                          unoptimized
                          referrerPolicy="no-referrer"
                          className="object-cover group-hover:scale-105 transition-transform duration-500"
                        />
                        <span className="absolute top-2 left-2 bg-primary text-white px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">
                          {art.category?.name || "Report"}
                        </span>
                      </div>
                    ) : (
                      <div className="aspect-[4/3] rounded-lg mb-3 bg-surface-low border border-border flex items-center justify-center p-3">
                        <span className="text-xs font-serif font-semibold text-muted text-center line-clamp-2">
                          {artAttr.sourceName}
                        </span>
                      </div>
                    )}

                    <h3 className="font-serif font-bold text-sm sm:text-base text-foreground group-hover:text-secondary transition-colors leading-snug mb-2 line-clamp-2">
                      <Link href={`/article/${art.slug}`}>
                        {art.title}
                      </Link>
                    </h3>

                    {art.description && (
                      <p className="text-xs text-muted line-clamp-3 mb-4 flex-1 leading-relaxed">
                        {art.description}
                      </p>
                    )}

                    <div className="flex items-center justify-between text-[11px] text-muted pt-2 border-t border-border mt-auto">
                      <span className="font-semibold text-foreground truncate max-w-[140px]">
                        {artAttr.byline}
                      </span>
                      <span>{formatTimestamp(art.published_at)}</span>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        </Container>
      )}

      {/* SECTION 3: DUAL-COLUMN COMPLEX (Politics & Policy + Most Read Sidebar) */}
      <Container>
        <section className="border-b border-border pb-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left Wing: US Politics & Policy Hub (8 Cols) */}
            <div className="lg:col-span-8 flex flex-col gap-6">
              <div className="flex items-center justify-between bg-surface-low px-4 py-2.5 rounded-lg border border-border">
                <h2 className="text-base font-serif font-bold text-foreground">
                  US Politics &amp; Policy
                </h2>
                <Link
                  href="/category/us"
                  className="text-xs font-bold text-secondary uppercase hover:underline"
                >
                  View All →
                </Link>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {secondaryArticles.length > 0 ? (
                  secondaryArticles.map((art) => {
                    const artAttr = resolveArticleAttribution(
                      art.author,
                      art.publisher_name,
                      art.source?.name,
                      art.source?.domain,
                      art.title
                    );
                    return (
                      <article
                        key={art.id}
                        className="bg-surface-lowest p-5 rounded-lg border border-border shadow-sm flex flex-col justify-between group hover:shadow-md transition-shadow"
                      >
                        <div>
                          <span className="text-[10px] font-bold text-secondary uppercase tracking-wider mb-1 block">
                            {art.category?.name || "Policy"}
                          </span>
                          <h3 className="font-serif font-bold text-base text-foreground group-hover:text-secondary transition-colors leading-snug mb-2">
                            <Link href={`/article/${art.slug}`}>
                              {art.title}
                            </Link>
                          </h3>
                          {art.description && (
                            <p className="text-xs text-muted line-clamp-3 mb-4 leading-relaxed">
                              {art.description}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center justify-between text-[11px] text-muted pt-2 border-t border-border">
                          <span>{artAttr.byline}</span>
                          <span className="font-medium text-secondary">{artAttr.sourceName}</span>
                        </div>
                      </article>
                    );
                  })
                ) : (
                  <div className="col-span-2 p-6 text-center text-xs text-muted border border-border rounded-lg bg-surface-lowest">
                    Additional policy coverage will appear here.
                  </div>
                )}
              </div>
            </div>

            {/* Right Wing: Most Read Sidebar (4 Cols) */}
            <aside className="lg:col-span-4 bg-surface-lowest p-6 rounded-xl border border-border shadow-sm flex flex-col">
              <div className="flex items-center justify-between pb-3 mb-4 border-b border-border">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-secondary" />
                  <h3 className="font-serif font-bold text-base text-foreground uppercase tracking-tight">
                    Most Read
                  </h3>
                </div>
                <span className="text-[10px] font-bold text-secondary uppercase">
                  Past 24 Hours
                </span>
              </div>

              <ol className="flex flex-col gap-4">
                {mostReadArticles.map((art, index) => {
                  const artAttr = resolveArticleAttribution(
                    art.author,
                    art.publisher_name,
                    art.source?.name,
                    art.source?.domain,
                    art.title
                  );
                  return (
                    <li key={art.id} className="flex items-start gap-4 group cursor-pointer">
                      <span className="font-serif text-2xl font-bold text-secondary/60 group-hover:text-secondary transition-colors shrink-0 leading-none">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <div className="flex flex-col">
                        <Link
                          href={`/article/${art.slug}`}
                          className="font-serif font-semibold text-sm text-foreground group-hover:text-secondary transition-colors leading-snug line-clamp-2"
                        >
                          {art.title}
                        </Link>
                        <span className="text-[11px] text-muted mt-1">
                          {art.category?.name || "National"} • {artAttr.sourceName}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </aside>
          </div>
        </section>
      </Container>

      {/* SECTION 4: EDITORIAL COVERAGE DESKS */}
      <Container>
        <section className="space-y-6">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div>
              <span className="text-[11px] font-bold text-secondary uppercase tracking-widest block">
                Editorial Structure
              </span>
              <h2 className="text-xl font-serif font-bold text-foreground">
                Editorial Coverage Desks
              </h2>
            </div>
            <Link
              href="/search"
              className="text-xs uppercase font-bold tracking-wider text-secondary hover:underline"
            >
              Search Coverage Archive →
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {EDITORIAL_DESKS.map((desk) => (
              <div
                key={desk.slug}
                className="border border-border bg-surface-lowest p-4 rounded-xl space-y-2 hover:border-secondary transition-colors flex flex-col justify-between"
              >
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-secondary">
                    Desk
                  </span>
                  <h3 className="text-base font-serif font-bold text-foreground">
                    <Link href={`/category/${desk.slug}`} className="hover:text-secondary transition-colors">
                      {desk.title}
                    </Link>
                  </h3>
                  <p className="text-xs text-muted leading-relaxed line-clamp-2">{desk.desc}</p>
                </div>
                <Link
                  href={`/category/${desk.slug}`}
                  className="inline-flex items-center space-x-1 text-xs font-semibold uppercase tracking-wider text-secondary hover:underline pt-2"
                >
                  <span>View Desk</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            ))}
          </div>
        </section>
      </Container>
    </div>
  );
}
