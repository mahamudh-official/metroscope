"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Container } from "@/components/Container";
import { Search, ArrowLeft, ArrowRight, Clock, AlertCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { Suspense, useState, useEffect, useCallback } from "react";
import { ArticleListItem, fetchArticles } from "@/lib/api";
import { resolveArticleAttribution } from "@/lib/attribution";

function SearchContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryParam = searchParams.get("q") || "";
  const pageParam = Math.max(1, parseInt(searchParams.get("page") || "1", 10) || 1);

  const [searchTerm, setSearchTerm] = useState(queryParam);
  const [results, setResults] = useState<ArticleListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    setSearchTerm(queryParam);
  }, [queryParam]);

  const executeSearch = useCallback(async (q: string, page: number) => {
    if (!q.trim()) {
      setResults([]);
      setTotal(0);
      setTotalPages(0);
      setHasError(false);
      return;
    }

    setIsLoading(true);
    setHasError(false);

    const data = await fetchArticles({ q: q.trim(), page, pageSize: 20 });
    if (data.error) {
      setResults([]);
      setTotal(0);
      setTotalPages(0);
      setHasError(true);
    } else {
      setResults(data.items || []);
      setTotal(data.total || 0);
      setTotalPages(data.total_pages || Math.ceil((data.total || 0) / 20));
      setHasError(false);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    executeSearch(queryParam, pageParam);
  }, [queryParam, pageParam, executeSearch]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchTerm.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchTerm.trim())}`);
    }
  };

  return (
    <Container className="py-8 space-y-8">
      <Link
        href="/"
        className="inline-flex items-center space-x-1.5 text-xs text-muted hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to Front Page</span>
      </Link>

      <div className="border-b border-border pb-6 space-y-4">
        <span className="text-xs font-bold uppercase tracking-widest text-secondary">
          News Archive
        </span>
        <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground">
          {queryParam ? `Search Results for "${queryParam}"` : "Search News Archive"}
        </h1>

        <form onSubmit={handleSearch} className="max-w-2xl flex gap-2 mt-4">
          <div className="relative flex-1">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search across headlines, topics, desks..."
              className="w-full pl-10 pr-4 py-3 text-sm rounded border border-border bg-surface text-foreground placeholder:text-muted focus:outline-none focus:border-secondary"
            />
            <Search className="w-4 h-4 text-muted absolute left-3.5 top-3.5 pointer-events-none" />
          </div>
          <button
            type="submit"
            className="px-5 py-3 text-xs font-bold uppercase tracking-wider rounded bg-secondary text-white hover:bg-secondary/90 transition-colors"
          >
            Search
          </button>
        </form>
      </div>

      <div className="space-y-6">
        <div className="flex items-center justify-between text-xs text-muted">
          <span>
            {queryParam
              ? isLoading
                ? "Searching archive..."
                : hasError
                  ? "Search service temporarily unavailable"
                  : `Showing ${results.length} of ${total} matching articles`
              : "Enter a keyword or phrase above"}
          </span>
          {totalPages > 1 && !hasError && (
            <span>
              Page {pageParam} of {totalPages}
            </span>
          )}
        </div>

        {isLoading ? (
          <div className="py-12 flex justify-center items-center space-x-2 text-muted text-sm">
            <Loader2 className="w-5 h-5 animate-spin text-secondary" />
            <span>Searching articles...</span>
          </div>
        ) : hasError ? (
          <div className="p-8 border border-border bg-surface-lowest rounded-lg text-center space-y-3">
            <AlertCircle className="w-8 h-8 mx-auto text-red-500" />
            <p className="font-semibold text-foreground text-sm">
              Unable to complete search request
            </p>
            <p className="text-xs text-muted max-w-md mx-auto">
              We could not reach the article archive right now. Please check your connection and try again.
            </p>
            <button
              type="button"
              onClick={() => executeSearch(queryParam, pageParam)}
              className="inline-flex items-center px-4 py-2 rounded bg-secondary text-white text-xs font-semibold hover:bg-secondary/90 transition-colors"
            >
              Retry Search
            </button>
          </div>
        ) : queryParam && results.length > 0 ? (
          <>
            <div className="space-y-6 divide-y divide-border">
              {results.map((art) => {
                const artAttr = resolveArticleAttribution(
                  art.author,
                  art.publisher_name,
                  art.source?.name,
                  art.source?.domain,
                  art.title
                );
                return (
                  <div key={art.id} className="pt-4 first:pt-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                      <span className="font-bold text-secondary uppercase">
                        {artAttr.sourceName}
                      </span>
                      {art.published_at && (
                        <>
                          <span>•</span>
                          <span className="flex items-center space-x-1">
                            <Clock className="w-3 h-3" />
                            <span>
                              {new Date(art.published_at).toLocaleDateString("en-US", {
                                month: "short",
                                day: "numeric",
                                year: "numeric",
                              })}
                            </span>
                          </span>
                        </>
                      )}
                      <span>•</span>
                      <span className="text-foreground font-medium">{artAttr.byline}</span>
                    </div>
                    <h3 className="text-lg font-serif font-bold text-foreground hover:text-secondary">
                      <Link href={`/article/${art.slug}`}>{art.title}</Link>
                    </h3>
                    {art.description && (
                      <p className="text-xs text-muted leading-relaxed line-clamp-3">
                        {art.description}
                      </p>
                    )}
                    <div className="pt-1">
                      <Link
                        href={`/article/${art.slug}`}
                        className="inline-flex items-center space-x-1 text-xs font-semibold text-secondary hover:underline"
                      >
                        <span>Read Full Coverage</span>
                        <ArrowRight className="w-3 h-3" />
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>

            {totalPages > 1 && (
              <nav
                aria-label="Search Pagination"
                className="flex items-center justify-between border-t border-border pt-6 text-xs font-semibold"
              >
                {pageParam > 1 ? (
                  <Link
                    href={`/search?q=${encodeURIComponent(queryParam)}&page=${pageParam - 1}`}
                    className="inline-flex items-center space-x-1.5 px-4 py-2 rounded border border-border bg-surface-lowest text-foreground hover:border-secondary transition-colors"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" />
                    <span>Previous Page</span>
                  </Link>
                ) : (
                  <span className="inline-flex items-center space-x-1.5 px-4 py-2 rounded border border-border text-muted opacity-50 cursor-not-allowed">
                    <ArrowLeft className="w-3.5 h-3.5" />
                    <span>Previous Page</span>
                  </span>
                )}

                <span className="text-muted">
                  Page {pageParam} of {totalPages}
                </span>

                {pageParam < totalPages ? (
                  <Link
                    href={`/search?q=${encodeURIComponent(queryParam)}&page=${pageParam + 1}`}
                    className="inline-flex items-center space-x-1.5 px-4 py-2 rounded border border-border bg-surface-lowest text-foreground hover:border-secondary transition-colors"
                  >
                    <span>Next Page</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                ) : (
                  <span className="inline-flex items-center space-x-1.5 px-4 py-2 rounded border border-border text-muted opacity-50 cursor-not-allowed">
                    <span>Next Page</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                )}
              </nav>
            )}
          </>
        ) : queryParam ? (
          <div className="p-8 border border-dashed border-border rounded-lg text-center text-muted text-sm space-y-2">
            <Search className="w-8 h-8 mx-auto text-secondary mb-2" />
            <p className="font-semibold text-foreground">No matching articles found</p>
            <p className="text-xs">
              Try searching with broader terms or keywords like &ldquo;economy&rdquo;, &ldquo;technology&rdquo;, or &ldquo;policy&rdquo;.
            </p>
          </div>
        ) : (
          <div className="p-8 border border-dashed border-border rounded-lg text-center text-muted text-sm">
            <Search className="w-8 h-8 mx-auto text-secondary mb-2" />
            <p>Enter keywords above to search headlines, summaries, and topics across all sections.</p>
          </div>
        )}
      </div>
    </Container>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="py-20 text-center text-sm text-muted">Loading search...</div>}>
      <SearchContent />
    </Suspense>
  );
}
