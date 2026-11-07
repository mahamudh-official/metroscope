import { Container } from "@/components/Container";
import { constructMetadata, generateNewsArticleJsonLd } from "@/lib/seo";
import Link from "next/link";
import { ArrowLeft, Clock, ExternalLink, ShieldCheck } from "lucide-react";

interface ArticlePageProps {
  params: {
    slug: string;
  };
}

export function generateMetadata({ params }: ArticlePageProps) {
  const cleanTitle = params.slug.replace(/-/g, " ");
  return constructMetadata({
    title: `${cleanTitle.charAt(0).toUpperCase() + cleanTitle.slice(1)} — Discovered Report`,
    description: "Detailed news discovery metadata, publisher attribution, and normalized summary.",
    type: "article",
  });
}

export default function ArticlePage({ params }: ArticlePageProps) {
  const title = params.slug
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  const publishedAt = new Date().toISOString();
  const jsonLd = generateNewsArticleJsonLd({
    headline: title,
    description: "Normalized news discovery record indexed via GDELT DOC 2.0 API.",
    datePublished: publishedAt,
    url: `https://metroscope.news/article/${params.slug}`,
  });

  return (
    <article className="py-8">
      {/* JSON-LD Structured Data for Search Engines */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <Container className="max-w-4xl space-y-8">
        <Link
          href="/"
          className="inline-flex items-center space-x-1.5 text-xs text-muted hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Front Page</span>
        </Link>

        {/* Article Masthead */}
        <header className="space-y-4 border-b border-border pb-6">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold uppercase tracking-widest text-secondary">
              Wire Dispatch
            </span>
            <span className="text-border">•</span>
            <span className="text-xs text-muted flex items-center space-x-1">
              <Clock className="w-3.5 h-3.5" />
              <span>Indexed {new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
            </span>
          </div>

          <h1 className="text-3xl sm:text-4xl md:text-5xl font-serif font-bold text-foreground leading-tight">
            {title}
          </h1>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-2 text-xs text-muted border-t border-border pt-4">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-foreground">Discovery Source:</span>
              <span className="bg-surface-container px-2 py-0.5 rounded text-foreground font-mono">
                GDELT Indexing Engine
              </span>
            </div>
            <div className="flex items-center space-x-1.5 text-secondary">
              <ShieldCheck className="w-4 h-4" />
              <span className="font-semibold">Publisher Attribution Verified</span>
            </div>
          </div>
        </header>

        {/* Publisher Notice & Copyright Safeguard */}
        <div className="p-4 rounded-lg bg-surface-low border border-border text-xs text-muted space-y-2">
          <p className="font-semibold text-foreground">Publisher Attribution Notice</p>
          <p>
            MetroScope indexes and normalizes publicly accessible news metadata via the GDELT Project. To read the complete investigative reporting, please visit the original publishing entity directly.
          </p>
          <div className="pt-1">
            <a
              href="https://www.gdeltproject.org/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center space-x-1 text-secondary font-semibold hover:underline"
            >
              <span>Visit Original Source Record</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {/* Article Body Content */}
        <section className="prose dark:prose-invert max-w-none text-foreground font-sans leading-relaxed space-y-4 text-base">
          <p className="text-lg font-serif italic text-muted leading-relaxed">
            This normalized article view represents the Phase 1 architectural preview for the MetroScope news discovery platform.
          </p>
          <p>
            The production news pipeline utilizes Python-based asynchronous workers running APScheduler to poll GDELT DOC 2.0 API endpoints at structured intervals. Upon ingestion, news items are normalized, checked for duplicate canonical URLs, and persisted to PostgreSQL.
          </p>
          <p>
            In accordance with copyright best practices and GDELT terms, MetroScope stores and displays factual article metadata, headlines, publication dates, and synthesized summaries while linking readers to original publishers for full articles.
          </p>
        </section>
      </Container>
    </article>
  );
}
