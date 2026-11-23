import React from "react";
import Link from "next/link";
import Image from "next/image";
import {
  Calendar,
  Camera,
  Clock,
  ExternalLink,
  Globe,
  TrendingUp,
  Zap,
} from "lucide-react";
import { ArticleDetail, ArticleListItem, ArticleInlineImage } from "@/lib/api";
import { ArticleHeroImage } from "@/components/ArticleHeroImage";
import { EDITORIAL_AUTHOR } from "@/lib/attribution";

interface CanonicalArticleViewProps {
  article: ArticleDetail;
  relatedArticles: ArticleListItem[];
}

export function resolveCleanSourceName(
  publisherName?: string | null,
  sourceName?: string | null,
  sourceDomain?: string | null,
  articleTitle?: string
): string {
  const candidates = [publisherName, sourceName];
  const cleanTitle = (articleTitle || "").trim().toLowerCase();

  for (const cand of candidates) {
    if (!cand || typeof cand !== "string") continue;
    const c = cand.trim();
    if (c.length < 2) continue;
    const lower = c.toLowerCase();
    if (lower.includes("homepage") || lower.endsWith(" - homepage")) continue;
    if (
      cleanTitle &&
      (lower === cleanTitle ||
        (lower.length > 15 && cleanTitle.includes(lower)) ||
        (cleanTitle.length > 15 && lower.includes(cleanTitle)))
    ) {
      continue;
    }
    // Clean pipe slogan or dash slogan
    let clean = c;
    if (clean.includes("|")) {
      const parts = clean.split("|").map((p) => p.trim());
      if (parts.length === 2) {
        clean = parts[1].length <= 30 && parts[1].length < parts[0].length ? parts[1] : parts[0];
      }
    }
    clean = clean.split(/\s*[-–—]\s*/)[0].trim();
    clean = clean.split(":")[0].trim();
    if (clean.length >= 2) return clean;
  }

  if (sourceDomain && typeof sourceDomain === "string" && sourceDomain.includes(".")) {
    const parts = sourceDomain.replace(/^www\./i, "").split(".");
    if (parts.length >= 2 && !["co", "com", "net", "org"].includes(parts[0])) {
      return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
    }
    return sourceDomain.replace(/^www\./i, "");
  }

  return "Original Publisher";
}

export function isGenuineSummary(summary?: string | null, title?: string): boolean {
  if (!summary || typeof summary !== "string") return false;
  const s = summary.trim();
  if (s.length < 20) return false;
  if (title && s.toLowerCase().replace(/\.+$/, "") === title.trim().toLowerCase().replace(/\.+$/, "")) {
    return false;
  }
  const lower = s.toLowerCase();
  if (
    lower.includes("comprehensive wire coverage") ||
    lower.includes("access the original publication") ||
    lower.includes("please enable cookies") ||
    lower.includes("sign in to continue") ||
    lower.includes("all rights reserved")
  ) {
    return false;
  }
  return true;
}

export function calculateReadingTime(text?: string | null, summary?: string | null): number {
  const content = (text && text.trim().length > 0 ? text : summary) || "";
  const words = content.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(words / 200));
}

function renderArticleParagraph(
  text: string,
  key: string | number,
  isFirst: boolean = false
): JSX.Element {
  const trimmed = text.trim();

  // Detect Markdown-style or standalone subheadings
  if (trimmed.startsWith("## ") || trimmed.startsWith("### ")) {
    const headingText = trimmed.replace(/^#{2,3}\s+/, "");
    return (
      <h2
        key={key}
        className="text-2xl sm:text-3xl font-serif font-bold text-foreground mt-8 mb-4 tracking-tight"
      >
        {headingText}
      </h2>
    );
  }

  // Detect short editorial subheading
  const isShortSubheading =
    trimmed.length > 5 &&
    trimmed.length < 75 &&
    !trimmed.endsWith(".") &&
    !trimmed.endsWith("?") &&
    !trimmed.endsWith("!") &&
    !trimmed.startsWith('"') &&
    !trimmed.startsWith("“") &&
    !trimmed.includes("\n") &&
    (trimmed.toUpperCase() === trimmed || /^[A-Z][A-Za-z0-9\s:,\-–—]+$/.test(trimmed));

  if (isShortSubheading) {
    return (
      <h3
        key={key}
        className="text-xl sm:text-2xl font-serif font-bold text-foreground mt-7 mb-3 tracking-tight"
      >
        {trimmed}
      </h3>
    );
  }

  // Detect blockquote or significant quotation
  const isBlockquote =
    trimmed.startsWith("> ") ||
    ((trimmed.startsWith('"') || trimmed.startsWith("“")) &&
      (trimmed.endsWith('"') || trimmed.endsWith("”")) &&
      trimmed.length > 40);

  if (isBlockquote) {
    const quoteText = trimmed.startsWith("> ")
      ? trimmed.slice(2).trim()
      : trimmed.replace(/^[“"]|[”"]$/g, "").trim();
    return (
      <blockquote
        key={key}
        className="my-6 pl-4 border-l-4 border-secondary/60 italic text-muted text-lg sm:text-xl font-serif leading-relaxed"
      >
        &ldquo;{quoteText}&rdquo;
      </blockquote>
    );
  }

  // Primary body paragraph with elegant drop cap on paragraph 1
  if (isFirst) {
    const firstChar = trimmed.charAt(0);
    const rest = trimmed.slice(1);
    const isLetter = /^[A-Za-z\u00C0-\u024F\u0400-\u04FF\u0600-\u06FF\u0980-\u09FF]$/.test(firstChar);

    if (isLetter) {
      return (
        <p
          key={key}
          className="text-lg sm:text-[19px] text-foreground font-serif leading-[1.8] tracking-normal mb-5 [overflow-wrap:break-word] [word-break:normal]"
        >
          <span className="float-left text-5xl sm:text-6xl font-serif font-bold text-primary mr-3.5 mt-1 leading-none select-none">
            {firstChar}
          </span>
          {rest}
        </p>
      );
    }
  }

  return (
    <p
      key={key}
      className="text-lg sm:text-[19px] text-foreground/90 font-serif leading-[1.8] tracking-normal mb-5 [overflow-wrap:break-word] [word-break:normal]"
    >
      {trimmed}
    </p>
  );
}

/**
 * Single Canonical Article Template for MetroScope.
 * 
 * Supports:
 * - Headline
 * - Category
 * - Publication date
 * - Publisher attribution
 * - Author (only when verified)
 * - Featured image (mandatory authorized HTTPS URL)
 * - Full article body (mandatory authorized multi-paragraph prose)
 * - Proper source attribution and external publisher link
 * 
 * Optional elements are conditionally hidden without layout breakage or synthetic content.
 */
export function CanonicalArticleView({
  article,
  relatedArticles,
}: CanonicalArticleViewProps): JSX.Element {
  const publishedAt = article.published_at;
  const canonicalUrl = article.canonical_url;
  const sourceName = resolveCleanSourceName(
    article.publisher_name,
    article.source?.name,
    article.source?.domain,
    article.title
  );

  const hasFullText = Boolean(
    article.content_display_authorized &&
      article.full_text &&
      article.full_text.trim().length > 0
  );

  const hasGenuineSummary = isGenuineSummary(article.description, article.title);

  const fullTextParagraphs = hasFullText
    ? (article.full_text || "")
        .split(/\n\s*\n/)
        .map((p) => p.trim())
        .filter((p) => p.length > 0)
    : [];

  const readingTimeMinutes = calculateReadingTime(article.full_text, article.description);
  const inlineImages: ArticleInlineImage[] = article.inline_images || [];

  return (
    <div className="w-full">
      {/* 1. Breadcrumbs & Category Bar matching Stitch */}
      <section className="w-full bg-surface-lowest border-b border-border py-2.5 shadow-xs overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <nav
            aria-label="Breadcrumb"
            className="flex items-center space-x-2 text-xs text-muted overflow-hidden"
          >
            <Link href="/" className="hover:text-foreground transition-colors shrink-0">
              Home
            </Link>
            <span className="shrink-0 text-border">/</span>
            {article.category && (
              <>
                <Link
                  href={`/category/${article.category.slug}`}
                  className="hover:text-foreground transition-colors uppercase tracking-wider font-semibold text-secondary shrink-0"
                >
                  {article.category.name}
                </Link>
                <span className="shrink-0 text-border">/</span>
              </>
            )}
            <span className="truncate text-foreground/80 font-medium">
              {article.title}
            </span>
          </nav>
          {article.category && (
            <div className="hidden sm:flex items-center gap-1.5 shrink-0">
              <span className="w-2 h-2 rounded-full bg-secondary" />
              <span className="font-bold text-[11px] uppercase tracking-wider text-secondary">
                {article.category.name}
              </span>
            </div>
          )}
        </div>
      </section>

      {/* 2. Main Article Layout Grid (8 Cols Primary + 4 Cols Rail) matching Stitch */}
      <main className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-start">
          {/* Primary Column (8 Columns) */}
          <section className="lg:col-span-8 flex flex-col gap-6">
            {/* Header & Deck Group */}
            <header className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center gap-2">
                {article.category && (
                  <span className="inline-flex items-center self-start px-2.5 py-0.5 bg-secondary/15 text-secondary border border-secondary/30 rounded text-[11px] font-bold uppercase tracking-wider">
                    {article.category.name}
                  </span>
                )}
                {article.is_breaking && (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-red-600 text-white animate-pulse">
                    <Zap className="w-3 h-3" />
                    <span>Breaking</span>
                  </span>
                )}
                {article.is_trending && (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-secondary/15 text-secondary border border-secondary/30">
                    <TrendingUp className="w-3 h-3" />
                    <span>Trending</span>
                  </span>
                )}
              </div>

              <h1 className="text-3xl sm:text-4xl lg:text-[42px] font-serif font-bold text-foreground leading-[1.2] tracking-tight [overflow-wrap:break-word] [word-break:normal]">
                {article.title}
              </h1>

              {/* Lede Summary (prominently above body for full-text articles) */}
              {hasFullText && hasGenuineSummary && (
                <div className="border-l-2 border-secondary/60 pl-4 py-1">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-secondary block mb-1">
                    Story Summary
                  </span>
                  <p className="text-lg sm:text-xl text-muted font-normal leading-relaxed">
                    {article.description}
                  </p>
                </div>
              )}

              {/* Author Attribution & Metadata Bar matching Stitch */}
              <div className="flex flex-wrap items-center justify-between gap-4 py-3 px-4 bg-surface-low rounded-lg border border-border/60">
                {(
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-full bg-surface-lowest text-secondary flex items-center justify-center border border-border shadow-xs shrink-0 font-bold text-xs">
                      MS
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs sm:text-sm font-bold text-foreground">
                        By {EDITORIAL_AUTHOR}
                      </span>
                      <span className="text-[11px] text-muted">
                        Source:{" "}
                        <a
                          href={canonicalUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-semibold text-secondary hover:underline inline-flex items-center gap-0.5 break-all"
                        >
                          <span>{sourceName}</span>
                          <ExternalLink className="w-2.5 h-2.5 text-muted shrink-0" />
                        </a>
                      </span>
                    </div>
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-4 text-xs text-muted">
                  <div className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-muted" />
                    <span>
                      {publishedAt
                        ? new Date(publishedAt).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })
                        : "Recent"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-secondary font-medium">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{readingTimeMinutes} min read</span>
                  </div>
                </div>
              </div>
            </header>

            {/* Supplementary Editorial Deck / Summary (Optional Lead when present in source) */}
            {hasGenuineSummary && (
              <div className="text-xl sm:text-2xl font-serif text-muted italic leading-relaxed mb-6 [overflow-wrap:break-word] [word-break:normal]">
                {article.description}
              </div>
            )}

            {/* Featured Media Section: Mandatory Authorized Hero Image */}
            {article.image_url && (
              <ArticleHeroImage
                src={article.image_url}
                alt={article.title}
                sourceName={sourceName}
                caption={article.image_caption}
                credit={article.image_credit}
                categoryName={article.category?.name}
              />
            )}

            {/* Body Editorial Prose: Single Canonical Layout */}
            <div className="flex flex-col gap-4 text-foreground max-w-3xl" id="article-content">
              {fullTextParagraphs.map((paragraph, index) => {
                const pElement = renderArticleParagraph(paragraph, `p-${index}`, index === 0);

                // Insert inline image after paragraph 1 if an authorized inline image is available
                if (index === 1 && inlineImages.length > 0 && inlineImages[0].url) {
                  const inlineImg = inlineImages[0];
                  return (
                    <React.Fragment key={`inline-wrapper-${index}`}>
                      {pElement}
                      <figure className="my-6 space-y-2">
                        <div className="relative aspect-[16/9] w-full overflow-hidden rounded-xl border border-border bg-surface-lowest shadow-sm">
                          <Image
                            src={inlineImg.url}
                            alt={inlineImg.caption || article.title}
                            fill
                            sizes="(max-width: 768px) 100vw, 768px"
                            className="object-cover"
                            unoptimized
                            referrerPolicy="no-referrer"
                          />
                        </div>
                        {(inlineImg.caption || inlineImg.credit) && (
                          <figcaption className="text-xs text-muted leading-relaxed flex flex-col sm:flex-row sm:items-center justify-between gap-1 px-1">
                            {inlineImg.caption && (
                              <span className="font-sans text-foreground/85">
                                {inlineImg.caption}
                              </span>
                            )}
                            {inlineImg.credit && (
                              <span className="inline-flex items-center space-x-1 text-[11px] font-sans text-muted italic">
                                <Camera className="w-3 h-3 text-secondary inline-block shrink-0" />
                                <span>{inlineImg.credit}</span>
                              </span>
                            )}
                          </figcaption>
                        )}
                      </figure>
                    </React.Fragment>
                  );
                }

                return pElement;
              })}

              {/* Provenance and Original Publication Link */}
              <div className="mt-8 pt-6 border-t border-border flex flex-wrap items-center justify-between gap-3 text-xs text-muted">
                <span>
                  Original reporting syndicated from{" "}
                  <strong className="text-foreground">{sourceName}</strong>.
                </span>
                <a
                  href={canonicalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center space-x-1.5 font-semibold text-secondary hover:underline"
                >
                  <span>View Original Article on {sourceName}</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>

            {/* Author card removed: all articles are authored by the MetroScope News Desk (shown in byline bar) */}
          </section>

          {/* Sidebar Rail (4 Columns) matching Stitch */}
          <aside className="lg:col-span-4 flex flex-col gap-6">
            {/* Daily Intelligence Newsletter Box */}
            <div className="p-6 bg-primary-container text-on-primary rounded-xl shadow-sm flex flex-col gap-4 relative overflow-hidden">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-secondary-container" />
                <span className="text-[11px] font-bold uppercase tracking-widest text-secondary-container">
                  Daily Intelligence
                </span>
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-serif font-bold text-white">
                  Stay Updated with MetroScope
                </h3>
                <p className="text-xs text-white/80 leading-relaxed">
                  Get the latest curated dispatches and verified news delivered directly to your inbox.
                </p>
              </div>
              <form
                className="flex flex-col gap-2 mt-1"
                action="#"
                method="GET"
              >
                <input
                  type="email"
                  placeholder="name@organization.com"
                  required
                  className="w-full px-3 py-2 rounded-lg bg-white/10 text-white placeholder:text-white/60 text-xs border border-white/20 focus:outline-none focus:border-secondary"
                />
                <button
                  type="submit"
                  className="w-full py-2 px-4 bg-secondary text-on-secondary rounded-lg text-xs uppercase tracking-wider font-bold hover:bg-secondary/90 transition-colors shadow-xs"
                >
                  Get Daily Briefing
                </button>
              </form>
            </div>

            {/* Trending Stories Rail */}
            {relatedArticles.length > 0 && (
              <div className="p-5 bg-surface-lowest rounded-xl border border-border shadow-xs flex flex-col gap-3">
                <div className="flex items-center justify-between pb-2 border-b border-border">
                  <h3 className="text-sm font-serif font-bold text-foreground uppercase tracking-tight">
                    Trending Coverage
                  </h3>
                  <span className="text-[10px] font-bold uppercase text-secondary tracking-wider">
                    Live
                  </span>
                </div>
                <div className="flex flex-col divide-y divide-border">
                  {relatedArticles.map((item) => (
                    <Link
                      key={item.id}
                      href={`/article/${item.slug}`}
                      className="group py-3.5 first:pt-1 last:pb-1 flex flex-col gap-1.5"
                    >
                      <div className="flex items-center gap-2 text-[11px] text-muted">
                        <span className="font-semibold text-secondary uppercase tracking-wider">
                          {item.category?.name || "News"}
                        </span>
                        <span>•</span>
                        <span>
                          {item.published_at
                            ? new Date(item.published_at).toLocaleDateString("en-US", {
                                month: "short",
                                day: "numeric",
                              })
                            : ""}
                        </span>
                      </div>
                      <h4 className="text-xs sm:text-sm font-serif font-bold text-foreground group-hover:text-secondary transition-colors line-clamp-2 leading-snug">
                        {item.title}
                      </h4>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}
