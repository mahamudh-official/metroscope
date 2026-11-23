import React from "react";
import { notFound } from "next/navigation";
import { fetchArticleBySlug, fetchRelatedArticles } from "@/lib/api";
import {
  constructMetadata,
  generateNewsArticleJsonLd,
  generateBreadcrumbJsonLd,
  safeJsonLd,
  siteConfig,
} from "@/lib/seo";
import { ArticleInteractions } from "@/components/ArticleInteractions";
import { EDITORIAL_AUTHOR } from "@/lib/attribution";
import {
  CanonicalArticleView,
  resolveCleanSourceName,
  calculateReadingTime,
} from "@/components/CanonicalArticleView";

interface ArticlePageProps {
  params: {
    slug: string;
  };
}

export const revalidate = 60;

export async function generateMetadata({ params }: ArticlePageProps) {
  const article = await fetchArticleBySlug(params.slug);
  if (!article) {
    return constructMetadata({
      title: "Article Not Found",
      description: "The requested article could not be found or is no longer available.",
      noIndex: true,
    });
  }

  const sourceName = resolveCleanSourceName(
    article.publisher_name,
    article.source?.name,
    article.source?.domain,
    article.title
  );

  return constructMetadata({
    title: article.title,
    description: article.description || `Read full coverage and reporting from ${sourceName}.`,
    image: article.image_url || undefined,
    canonicalUrl: article.canonical_url,
    type: "article",
  });
}

/**
 * Canonical MetroScope Article Route.
 * 
 * Enforces exactly ONE single article detail template for all published news.
 * Uses CanonicalArticleView component.
 */
export default async function ArticlePage({ params }: ArticlePageProps) {
  const article = await fetchArticleBySlug(params.slug);

  if (!article) {
    notFound();
  }

  const relatedArticles = await fetchRelatedArticles(article.slug, 5);

  const publishedAt = article.published_at || new Date().toISOString();
  const canonicalUrl = article.canonical_url;
  const sourceName = resolveCleanSourceName(
    article.publisher_name,
    article.source?.name,
    article.source?.domain,
    article.title
  );
  const sourceDomain = article.source?.domain || "themetroscope.com";
  const readingTimeMinutes = calculateReadingTime(article.full_text, article.description);

  const articleJsonLd = generateNewsArticleJsonLd({
    headline: article.title,
    description: article.description || `Reporting by ${sourceName}.`,
    datePublished: publishedAt,
    dateModified: article.updated_at,
    authorName: EDITORIAL_AUTHOR,
    sourceName,
    sourceDomain,
    canonicalUrl,
    url: `${siteConfig.url}/article/${article.slug}`,
  });

  const breadcrumbsJsonLd = generateBreadcrumbJsonLd([
    { name: "Home", item: "/" },
    {
      name: article.category?.name || "News",
      item: `/category/${article.category?.slug || "us"}`,
    },
    { name: article.title, item: `/article/${article.slug}` },
  ]);

  return (
    <article className="pb-12 sm:pb-16 overflow-hidden break-all">
      {/* Search Engine Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLd(articleJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLd(breadcrumbsJsonLd) }}
      />

      {/* Top Reading Progress Bar (Fixed Top Accent) */}
      <ArticleInteractions title={article.title} readingTimeMinutes={readingTimeMinutes} />

      {/* Single Canonical Article Template */}
      <CanonicalArticleView article={article} relatedArticles={relatedArticles} />
    </article>
  );
}
