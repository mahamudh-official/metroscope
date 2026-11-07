import { Container } from "@/components/Container";
import { constructMetadata } from "@/lib/seo";
import Link from "next/link";
import { ArrowLeft, Clock, ExternalLink } from "lucide-react";
import { notFound } from "next/navigation";

const CATEGORY_NAMES: Record<string, string> = {
  "us-news": "US News",
  "world": "World News",
  "technology": "Technology & AI",
  "business": "Business & Economy",
  "markets": "Financial Markets",
  "politics": "Politics & Governance",
  "science": "Science & Exploration",
  "culture": "Culture & Society",
  "opinion": "Editorial & Opinion",
};

interface CategoryPageProps {
  params: {
    slug: string;
  };
}

export function generateMetadata({ params }: CategoryPageProps) {
  const categoryName = CATEGORY_NAMES[params.slug] || params.slug;
  return constructMetadata({
    title: `${categoryName} — News Coverage`,
    description: `Latest real-time discovery and editorial wire records for ${categoryName}.`,
  });
}

export default function CategoryPage({ params }: CategoryPageProps) {
  const categoryName = CATEGORY_NAMES[params.slug];

  if (!categoryName) {
    notFound();
  }

  return (
    <Container className="py-8 space-y-8">
      {/* Category Header */}
      <div className="border-b border-border pb-6">
        <Link
          href="/"
          className="inline-flex items-center space-x-1.5 text-xs text-muted hover:text-foreground mb-4 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Front Page</span>
        </Link>
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold uppercase tracking-widest text-secondary">
            Editorial Desk
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground mt-1">
          {categoryName}
        </h1>
        <p className="text-sm text-muted mt-2">
          Real-time aggregated discovery wire covering major verified updates in {categoryName}.
        </p>
      </div>

      {/* Wire List Foundation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <h2 className="text-xs font-bold uppercase tracking-wider text-muted border-b border-border pb-2">
            Discovered Reports
          </h2>

          <div className="space-y-6 divide-y divide-border">
            <article className="pt-6 first:pt-0 space-y-2">
              <div className="flex items-center space-x-2 text-[11px] text-muted">
                <span className="font-bold text-secondary uppercase">Discovered Source</span>
                <span>•</span>
                <span className="flex items-center space-x-1">
                  <Clock className="w-3 h-3" />
                  <span>Real-time Normalized</span>
                </span>
              </div>
              <h3 className="text-xl font-serif font-bold text-foreground hover:text-secondary">
                <Link href={`/article/${params.slug}-sample-dispatch`}>
                  {categoryName} Sector Analysis: High-Frequency Data Trends and Structural Evolution
                </Link>
              </h3>
              <p className="text-sm text-muted leading-relaxed">
                Automated index record tracking verified publication signals across domestic and international reporting agencies. Full normalization pipeline ensures structural deduplication.
              </p>
              <div className="pt-2 flex items-center space-x-4 text-xs">
                <Link
                  href={`/article/${params.slug}-sample-dispatch`}
                  className="text-secondary font-semibold hover:underline inline-flex items-center space-x-1"
                >
                  <span>Read Normalized Dispatch</span>
                  <ExternalLink className="w-3 h-3" />
                </Link>
              </div>
            </article>
          </div>
        </div>

        {/* Desk Metadata Sidebar */}
        <aside className="border-t lg:border-t-0 lg:border-l border-border lg:pl-6 space-y-6">
          <div className="border border-border p-4 rounded bg-surface-lowest space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
              About This Desk
            </h3>
            <p className="text-xs text-muted leading-relaxed">
              Records under {categoryName} are indexed from the GDELT DOC 2.0 API and categorized according to semantic news taxonomy.
            </p>
          </div>
        </aside>
      </div>
    </Container>
  );
}
