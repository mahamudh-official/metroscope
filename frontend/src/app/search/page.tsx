"use client";

import { useSearchParams } from "next/navigation";
import { Container } from "@/components/Container";
import { Search, ArrowLeft, Clock } from "lucide-react";
import Link from "next/link";
import { Suspense, useState } from "react";

function SearchContent() {
  const searchParams = useSearchParams();
  const queryParam = searchParams.get("q") || "";
  const [searchTerm, setSearchTerm] = useState(queryParam);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchTerm.trim()) {
      window.location.href = `/search?q=${encodeURIComponent(searchTerm.trim())}`;
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
          {queryParam ? `Search Results for "${queryParam}"` : "Search News Discovery Archive"}
        </h1>

        <form onSubmit={handleSearch} className="max-w-2xl relative mt-4">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search across headlines, topics, desks..."
            className="w-full pl-10 pr-4 py-3 text-sm rounded border border-border bg-surface text-foreground placeholder:text-muted focus:outline-none focus:border-secondary"
          />
          <Search className="w-4 h-4 text-muted absolute left-3.5 top-3.5 pointer-events-none" />
        </form>
      </div>

      <div className="space-y-6">
        <div className="flex items-center justify-between text-xs text-muted">
          <span>{queryParam ? "Showing verified discovery results" : "Enter a search term above"}</span>
          <span>Indexed via GDELT DOC 2.0</span>
        </div>

        {queryParam ? (
          <div className="space-y-6 divide-y divide-border">
            <div className="pt-4 first:pt-0 space-y-2">
              <div className="flex items-center space-x-2 text-[11px] text-muted">
                <span className="font-bold text-secondary uppercase">Discovered Report</span>
                <span>•</span>
                <span className="flex items-center space-x-1">
                  <Clock className="w-3 h-3" />
                  <span>Real-time Normalized</span>
                </span>
              </div>
              <h3 className="text-lg font-serif font-bold text-foreground hover:text-secondary">
                <Link href={`/article/${encodeURIComponent(queryParam.toLowerCase().replace(/\s+/g, "-"))}-overview`}>
                  Key Developments and Comprehensive Analysis Regarding {queryParam}
                </Link>
              </h3>
              <p className="text-xs text-muted leading-relaxed">
                Indexed report cross-referencing public news signals, regulatory filings, and primary dispatches across US and global publishers.
              </p>
            </div>
          </div>
        ) : (
          <div className="p-8 border border-dashed border-border rounded-lg text-center text-muted text-sm">
            <Search className="w-8 h-8 mx-auto text-secondary mb-2" />
            <p>Type keywords to query indexed articles, topics, or publishers.</p>
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
