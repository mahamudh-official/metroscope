import Link from "next/link";
import { Container } from "@/components/Container";
import { Home, Search, FileQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <Container className="py-24 text-center">
      <div className="max-w-lg mx-auto space-y-6">
        <div className="w-16 h-16 rounded-full bg-secondary/10 border border-secondary/30 flex items-center justify-center mx-auto text-secondary">
          <FileQuestion className="w-8 h-8" />
        </div>

        <span className="text-xs font-bold uppercase tracking-widest text-secondary block">
          Error 404 • Page Not Found
        </span>

        <h1 className="text-4xl sm:text-5xl font-serif font-bold text-foreground">
          Page Not Found
        </h1>

        <p className="text-sm text-muted leading-relaxed">
          The article or section you requested could not be found. It may have been moved or is no longer available.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4">
          <Link
            href="/"
            className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-6 py-2.5 rounded bg-metro-navy dark:bg-primary-container text-white text-xs font-bold uppercase tracking-wider hover:opacity-90 transition-opacity"
          >
            <Home className="w-4 h-4" />
            <span>Return to Front Page</span>
          </Link>
          <Link
            href="/search"
            className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-6 py-2.5 rounded border border-border text-foreground text-xs font-bold uppercase tracking-wider hover:bg-surface-container transition-colors"
          >
            <Search className="w-4 h-4" />
            <span>Search News Archive</span>
          </Link>
        </div>
      </div>
    </Container>
  );
}
