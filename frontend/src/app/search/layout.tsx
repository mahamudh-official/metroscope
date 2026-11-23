import type { Metadata } from "next";
import { constructMetadata } from "@/lib/seo";

export const metadata: Metadata = constructMetadata({
  title: "Search News Archive",
  description: "Search the real-time MetroScope automated news index by topic, publisher, or keyword.",
  canonicalUrl: "/search",
  noIndex: true, // Prevent search result index bloat and crawler trap
});

export default function SearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
