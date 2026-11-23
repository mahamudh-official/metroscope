import { fetchArticles } from "@/lib/api";
import { siteConfig } from "@/lib/seo";

export const dynamic = "force-dynamic";

function escapeXml(unsafe: string): string {
  return unsafe.replace(/[<>&'"]/g, (c) => {
    switch (c) {
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case "&":
        return "&amp;";
      case "'":
        return "&apos;";
      case '"':
        return "&quot;";
      default:
        return c;
    }
  });
}

export async function GET() {
  const articlesResponse = await fetchArticles({ pageSize: 30 });
  const articles = articlesResponse.items || [];
  const buildDate = new Date().toUTCString();

  const itemsXml = articles
    .map((art) => {
      const pubDate = art.published_at ? new Date(art.published_at).toUTCString() : buildDate;
      const articleUrl = `${siteConfig.url}/article/${art.slug}`;
      const sourceName = escapeXml(art.publisher_name || art.source?.name || art.source?.domain || "Original Publisher");
      const title = escapeXml(art.title);
      const description = escapeXml(art.description || "");
      const category = art.category?.name ? `<category>${escapeXml(art.category.name)}</category>` : "";

      return `
    <item>
      <title>${title}</title>
      <link>${articleUrl}</link>
      <guid isPermaLink="true">${articleUrl}</guid>
      <description>${description}</description>
      <pubDate>${pubDate}</pubDate>
      <source url="${escapeXml(art.canonical_url)}">${sourceName}</source>
      ${category}
    </item>`;
    })
    .join("");

  const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(siteConfig.name)}</title>
    <link>${siteConfig.url}</link>
    <description>${escapeXml(siteConfig.description)}</description>
    <language>en-US</language>
    <lastBuildDate>${buildDate}</lastBuildDate>
    <atom:link href="${siteConfig.url}/feed.xml" rel="self" type="application/rss+xml"/>
    ${itemsXml}
  </channel>
</rss>`;

  return new Response(rss, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, s-maxage=1800, stale-while-revalidate=600",
    },
  });
}
