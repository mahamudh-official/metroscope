import type { Metadata } from "next";

export const siteConfig = {
  name: "MetroScope",
  tagline: "National & International News",
  description: "US-focused digital news publication presenting curated headlines, permitted summaries, and direct attribution to original reporting across politics, business, technology, science, and world affairs.",
  url: process.env.NEXT_PUBLIC_SITE_URL || "https://themetroscope.com",
  ogImage: "/logo.png",
};

export function constructMetadata({
  title,
  description = siteConfig.description,
  image = siteConfig.ogImage,
  canonicalUrl,
  type = "website",
  noIndex = false,
}: {
  title?: string;
  description?: string;
  image?: string;
  canonicalUrl?: string;
  type?: "website" | "article";
  noIndex?: boolean;
} = {}): Metadata {
  const fullTitle = title
    ? `${title} | ${siteConfig.name}`
    : `${siteConfig.name} — ${siteConfig.tagline}`;

  const canonical = canonicalUrl ? (canonicalUrl.startsWith("http") ? canonicalUrl : `${siteConfig.url}${canonicalUrl}`) : siteConfig.url;

  return {
    title: fullTitle,
    description,
    metadataBase: new URL(siteConfig.url),
    alternates: {
      canonical,
    },
    openGraph: {
      title: fullTitle,
      description,
      type,
      url: canonical,
      siteName: siteConfig.name,
      images: [
        {
          url: image.startsWith("http") ? image : `${siteConfig.url}${image}`,
          width: 1200,
          height: 630,
          alt: fullTitle,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description,
      images: [image.startsWith("http") ? image : `${siteConfig.url}${image}`],
    },
    robots: {
      index: !noIndex,
      follow: true,
      googleBot: {
        index: !noIndex,
        follow: true,
        "max-video-preview": -1,
        "max-image-preview": "large",
        "max-snippet": -1,
      },
    },
  };
}

export function generateOrganizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "NewsMediaOrganization",
    name: siteConfig.name,
    url: siteConfig.url,
    logo: {
      "@type": "ImageObject",
      url: `${siteConfig.url}/logo.png`,
      width: 512,
      height: 512,
    },
    description: siteConfig.description,
    publishingPrinciples: `${siteConfig.url}/about`,
  };
}

export function generateNewsArticleJsonLd({
  headline,
  description,
  datePublished,
  dateModified,
  authorName,
  sourceName,
  sourceDomain,
  canonicalUrl,
  url,
}: {
  headline: string;
  description: string;
  datePublished: string;
  dateModified?: string | null;
  authorName?: string | null;
  sourceName?: string;
  sourceDomain?: string;
  canonicalUrl?: string;
  url: string;
}) {
  const sourceOrgUrl = sourceDomain
    ? sourceDomain.startsWith("http")
      ? sourceDomain
      : `https://${sourceDomain}`
    : undefined;

  const authors = authorName
    ? [
        {
          "@type": "Person",
          name: authorName,
        },
      ]
    : [
        {
          "@type": "Organization",
          name: sourceName || siteConfig.name,
          url: sourceOrgUrl,
        },
      ];

  return {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline,
    description,
    image: [`${siteConfig.url}/logo.png`],
    datePublished,
    dateModified: dateModified || datePublished,
    isBasedOn: canonicalUrl || undefined,
    author: authors,
    publisher: {
      "@type": "NewsMediaOrganization",
      name: siteConfig.name,
      url: siteConfig.url,
      logo: {
        "@type": "ImageObject",
        url: `${siteConfig.url}/logo.png`,
      },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": url,
    },
  };
}

export function generateBreadcrumbJsonLd(
  items: Array<{ name: string; item: string }>
) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((crumb, idx) => ({
      "@type": "ListItem",
      position: idx + 1,
      name: crumb.name,
      item: crumb.item.startsWith("http") ? crumb.item : `${siteConfig.url}${crumb.item}`,
    })),
  };
}

/**
 * Safely serializes structured data to JSON for embedding within HTML <script type="application/ld+json">.
 * Replaces HTML-sensitive characters (<, >, &, \u2028, \u2029) with their Unicode escape sequences
 * to prevent HTML parsers from breaking out of the script block (e.g. via </script>) or interpreting
 * raw HTML markup.
 */
export function safeJsonLd(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}
