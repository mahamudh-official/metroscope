import { MetadataRoute } from "next";
import { siteConfig } from "@/lib/seo";
import { fetchArticles, fetchCategories } from "@/lib/api";

export const revalidate = 3600; // Regenerate sitemap hourly

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = siteConfig.url;
  const now = new Date();

  // Core static routes (Note: /search is excluded because it is configured with noindex)
  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: baseUrl,
      lastModified: now,
      changeFrequency: "always",
      priority: 1.0,
    },
    {
      url: `${baseUrl}/about`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.5,
    },
    {
      url: `${baseUrl}/contact`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.4,
    },
    {
      url: `${baseUrl}/privacy`,
      lastModified: now,
      changeFrequency: "yearly",
      priority: 0.3,
    },
    {
      url: `${baseUrl}/terms`,
      lastModified: now,
      changeFrequency: "yearly",
      priority: 0.3,
    },
  ];

  // Editorial categories
  const categories = await fetchCategories();
  const categorySlugs =
    categories.length > 0
      ? categories.map((cat) => cat.slug)
      : [
          "us",
          "world",
          "politics",
          "business",
          "technology",
          "science",
          "health",
          "environment",
          "sports",
          "entertainment",
        ];
  const categoryRoutes: MetadataRoute.Sitemap = categorySlugs.map((slug) => ({
    url: `${baseUrl}/category/${slug}`,
    lastModified: now,
    changeFrequency: "hourly",
    priority: 0.9,
  }));

  // Latest indexed articles
  const articlesResponse = await fetchArticles({ pageSize: 50 });
  const articleRoutes: MetadataRoute.Sitemap = (articlesResponse.items || []).map((art) => ({
    url: `${baseUrl}/article/${art.slug}`,
    lastModified: art.published_at ? new Date(art.published_at) : now,
    changeFrequency: "daily",
    priority: 0.7,
  }));

  return [...staticRoutes, ...categoryRoutes, ...articleRoutes];
}
