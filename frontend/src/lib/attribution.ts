/**
 * MetroScope Editorial Attribution.
 *
 * Every article is authored by the MetroScope News Desk, regardless of any
 * byline supplied by the upstream provider. The original publisher/source is
 * kept as a separate attribution field and is never merged with the author.
 */

export const EDITORIAL_AUTHOR = "MetroScope News Desk";

export interface ResolvedAttribution {
  author: string;
  byline: string;
  sourceName: string;
  isDesk: boolean;
  avatarInitials: string;
}

export function resolveArticleAttribution(
  _author?: string | null,
  publisherName?: string | null,
  sourceName?: string | null,
  domain?: string | null,
  _title?: string
): ResolvedAttribution {
  let cleanPublisher = (publisherName || sourceName || domain || "Original Publisher").trim();
  if (cleanPublisher.includes("|")) {
    cleanPublisher = cleanPublisher.split("|")[0].trim();
  }
  if (cleanPublisher.includes(" - ")) {
    cleanPublisher = cleanPublisher.split(" - ")[0].trim();
  }
  if (!cleanPublisher || cleanPublisher.length < 2) {
    cleanPublisher = "Original Publisher";
  }

  return {
    author: EDITORIAL_AUTHOR,
    byline: EDITORIAL_AUTHOR,
    sourceName: cleanPublisher,
    isDesk: true,
    avatarInitials: "MS",
  };
}
