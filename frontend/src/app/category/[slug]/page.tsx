import { Container } from "@/components/Container";
import { constructMetadata, generateBreadcrumbJsonLd, safeJsonLd } from "@/lib/seo";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, ArrowRight, Clock, TrendingUp, Zap, ShieldCheck } from "lucide-react";
import { fetchCategoryArticles } from "@/lib/api";
import { resolveArticleAttribution } from "@/lib/attribution";

const CATEGORY_NAMES: Record<string, string> = {
  "us": "US News",
  "world": "World News",
  "technology": "Technology & AI",
  "business": "Business & Economy",
  "politics": "Politics & Governance",
  "science": "Science & Exploration",
  "health": "Health & Medicine",
  "environment": "Environment & Climate",
  "sports": "Sports",
  "entertainment": "Culture & Entertainment",
};

const ALIAS_REDIRECTS: Record<string, string> = {
  "us-news": "us",
  "markets": "business",
  "culture": "entertainment",
};

interface CategoryPageProps {
  params: {
    slug: string;
  };
  searchParams?: {
    page?: string;
  };
}

export function generateMetadata({ params }: CategoryPageProps) {
  const canonicalSlug = ALIAS_REDIRECTS[params.slug] || params.slug;
  const categoryName = CATEGORY_NAMES[canonicalSlug];
  if (!categoryName) {
    return constructMetadata({
      title: "Category Not Found",
      description: "The requested news coverage category could not be located.",
      noIndex: true,
    });
  }

  return constructMetadata({
    title: `${categoryName} — News Coverage`,
    description: `Latest reporting, summaries, and publisher coverage in ${categoryName}.`,
    canonicalUrl: `/category/${canonicalSlug}`,
  });
}

export const revalidate = 60;

export default async function CategoryPage({ params, searchParams }: CategoryPageProps) {
  if (params.slug in ALIAS_REDIRECTS) {
    redirect(`/category/${ALIAS_REDIRECTS[params.slug]}`);
  }

  const categoryName = CATEGORY_NAMES[params.slug];
  if (!categoryName) {
    notFound();
  }

  const currentPage = Math.max(1, parseInt(searchParams?.page || "1", 10) || 1);
  const data = await fetchCategoryArticles(params.slug, { page: currentPage, pageSize: 20 });
  const articles = data.items || [];
  const totalPages = data.total_pages || Math.ceil((data.total || 0) / 20);

  const breadcrumbsJsonLd = generateBreadcrumbJsonLd([
    { name: "Home", item: "/" },
    { name: categoryName, item: `/category/${params.slug}` },
  ]);

  return (
    <Container className="py-8 space-y-8">
      {/* Search Engine Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLd(breadcrumbsJsonLd) }}
      />

      {/* Category Header */}
      <div className="border-b border-border pb-6">
        <Link
          href="/"
          className="inline-flex items-center space-x-1.5 text-xs text-muted hover:text-foreground mb-4 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Front Page</span>
        </Link>
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold uppercase tracking-widest text-secondary">
            Editorial Desk
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground mt-1">
          {categoryName}
        </h1>
        <p className="text-sm text-muted mt-2">
          Curated headlines and authoritative coverage from verified newsrooms covering {categoryName}.
        </p>
      </div>

      {/* Article List */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between border-b border-border pb-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-muted">
              Latest Stories ({data.total || articles.length})
            </h2>
            {totalPages > 1 && (
              <span className="text-xs text-muted">
                Page {currentPage} of {totalPages}
              </span>
            )}
          </div>

          <div className="space-y-6 divide-y divide-border">
            {articles.length > 0 ? (
              articles.map((art) => {
                const artAttr = resolveArticleAttribution(
                  art.author,
                  art.publisher_name,
                  art.source?.name,
                  art.source?.domain,
                  art.title
                );
                return (
                  <article key={art.id} className="pt-6 first:pt-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                      {art.is_breaking && (
                        <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-red-600 text-white">
                          <Zap className="w-2.5 h-2.5" />
                          <span>Breaking</span>
                        </span>
                      )}
                      {art.is_trending && (
                        <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-secondary/15 text-secondary border border-secondary/30">
                          <TrendingUp className="w-2.5 h-2.5" />
                          <span>Trending</span>
                        </span>
                      )}
                      <span className="font-bold text-secondary uppercase">
                        {artAttr.sourceName}
                      </span>
                      {art.published_at && (
                        <>
                          <span>•</span>
                          <span className="flex items-center space-x-1">
                            <Clock className="w-3 h-3" />
                            <span>
                              {new Date(art.published_at).toLocaleDateString("en-US", {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          </span>
                        </>
                      )}
                      <span>•</span>
                      <span className="text-foreground font-medium">{artAttr.byline}</span>
                    </div>

                    <h3 className="text-xl font-serif font-bold text-foreground hover:text-secondary">
                      <Link href={`/article/${art.slug}`}>{art.title}</Link>
                    </h3>

                    {art.description && (
                      <p className="text-sm text-muted leading-relaxed line-clamp-3">
                        {art.description}
                      </p>
                    )}

                    <div className="pt-2 flex items-center space-x-4 text-xs">
                      <Link
                        href={`/article/${art.slug}`}
                        className="text-secondary font-semibold hover:underline inline-flex items-center space-x-1"
                      >
                        <span>Read Full Coverage</span>
                        <ArrowRight className="w-3 h-3" />
                      </Link>
                    </div>
                  </article>
                );
              })
            ) : (
              <div className="py-12 px-6 border border-border bg-surface-lowest rounded-xl text-center space-y-4">
                <div className="w-12 h-12 mx-auto rounded-full bg-secondary/10 text-secondary flex items-center justify-center">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-lg font-serif font-bold text-foreground">
                    No Stories Currently Published in {categoryName}
                  </h3>
                  <p className="text-xs text-muted max-w-md mx-auto leading-relaxed">
                    Incoming dispatches for this desk are actively processed under MetroScope&apos;s strict pre-insertion editorial and rights authorization gate. Verified articles will appear here following the next scheduled ingestion cycle.
                  </p>
                </div>
                <div className="pt-2">
                  <Link
                    href="/"
                    className="inline-flex items-center space-x-1 text-xs font-bold uppercase tracking-wider text-secondary hover:underline"
                  >
                    <span>Return to Front Page</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            )}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <nav
              aria-label="Category Pagination"
              className="flex items-center justify-between border-t border-border pt-6 text-xs font-semibold"
            >
              {currentPage > 1 ? (
                <Link
                  href={`/category/${params.slug}?page=${currentPage - 1}`}
                  className="inline-flex items-center space-x-1.5 px-4 py-2 rounded border border-border bg-surface-lowest text-foreground hover:border-secondary transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Previous Page</span>
                </Link>
              ) : (
                <span className="inline-flex items-center space-x-1.5 px-4 py-2 rounded border border-border text-muted opacity-50 cursor-not-allowed">
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Previous Page</span>
                </span>
              )}

              <span className="text-muted">
                Page {currentPage} of {totalPages}
              </span>

              {currentPage < totalPages ? (
                <Link
                  href={`/category/${params.slug}?page=${currentPage + 1}`}
                  className="inline-flex items-center space-x-1.5 px-4 py-2 rounded border border-border bg-surface-lowest text-foreground hover:border-secondary transition-colors"
                >
                  <span>Next Page</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              ) : (
                <span className="inline-flex items-center space-x-1.5 px-4 py-2 rounded border border-border text-muted opacity-50 cursor-not-allowed">
                  <span>Next Page</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </span>
              )}
            </nav>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <div className="p-6 bg-surface-lowest border border-border rounded-xl space-y-4">
            <h3 className="text-sm font-serif font-bold text-foreground uppercase tracking-wider">
              Desk Coverage Standards
            </h3>
            <p className="text-xs text-muted leading-relaxed">
              Every story published on the {categoryName} desk is attributed directly to its originating publisher with verified bylines, explicit republication permissions, and strict provenance integrity.
            </p>
            <div className="pt-2 border-t border-border/60">
              <Link
                href="/about"
                className="text-xs font-semibold text-secondary hover:underline inline-flex items-center space-x-1"
              >
                <span>Read Editorial Policy</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>

          <div className="p-6 bg-surface-lowest border border-border rounded-xl space-y-4">
            <h3 className="text-sm font-serif font-bold text-foreground uppercase tracking-wider">
              Other Editorial Desks
            </h3>
            <ul className="space-y-2 text-xs">
              {Object.entries(CATEGORY_NAMES)
                .filter(([slug]) => slug !== params.slug)
                .slice(0, 6)
                .map(([slug, name]) => (
                  <li key={slug}>
                    <Link
                      href={`/category/${slug}`}
                      className="text-muted hover:text-secondary transition-colors block py-1"
                    >
                      {name} →
                    </Link>
                  </li>
                ))}
            </ul>
          </div>
        </div>
      </div>
    </Container>
  );
}
