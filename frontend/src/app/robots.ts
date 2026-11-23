import { MetadataRoute } from "next";
import { siteConfig } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = siteConfig.url;

  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/search", "/unsubscribe", "/verify-subscription"],
    },
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
