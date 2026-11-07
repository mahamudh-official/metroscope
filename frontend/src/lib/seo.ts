import type { Metadata } from "next";

export const siteConfig = {
  name: "MetroScope",
  tagline: "Automated US & Global News Discovery",
  description: "MetroScope is a US-focused editorial news discovery platform providing real-time coverage across politics, business, technology, world affairs, and culture.",
  url: process.env.NEXT_PUBLIC_SITE_URL || "https://metroscope.news",
  ogImage: "/logo.png",
};

export function constructMetadata({
  title,
  description = siteConfig.description,
  image = siteConfig.ogImage,
  canonicalUrl,
  type = "website",
}: {
  title?: string;
  description?: string;
  image?: string;
  canonicalUrl?: string;
  type?: "website" | "article";
} = {}): Metadata {
  const fullTitle = title ? `${title} | ${siteConfig.name}` : `${siteConfig.name} — ${siteConfig.tagline}`;

  return {
    title: fullTitle,
    description,
    metadataBase: new URL(siteConfig.url),
    alternates: {
      canonical: canonicalUrl || siteConfig.url,
    },
    openGraph: {
      title: fullTitle,
      description,
      type,
      url: canonicalUrl || siteConfig.url,
      siteName: siteConfig.name,
      images: [
        {
          url: image,
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
      images: [image],
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export function generateNewsArticleJsonLd({
  headline,
  description,
  datePublished,
  dateModified,
  authorName,
  publisherName = siteConfig.name,
  url,
  imageUrl,
}: {
  headline: string;
  description: string;
  datePublished: string;
  dateModified?: string;
  authorName?: string;
  publisherName?: string;
  url: string;
  imageUrl?: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline,
    description,
    image: imageUrl ? [imageUrl] : undefined,
    datePublished,
    dateModified: dateModified || datePublished,
    author: [
      {
        "@type": "Person",
        name: authorName || "MetroScope Staff",
      },
    ],
    publisher: {
      "@type": "Organization",
      name: publisherName,
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
