import { Container } from "@/components/Container";
import { constructMetadata } from "@/lib/seo";

export const metadata = constructMetadata({
  title: "Terms & Conditions",
  description: "MetroScope Terms & Conditions governing discovery services, copyright, and platform usage.",
  canonicalUrl: "/terms",
});

export default function TermsPage() {
  return (
    <Container className="py-12 max-w-4xl space-y-8">
      <div className="border-b border-border pb-6 space-y-2">
        <span className="text-xs font-bold uppercase tracking-widest text-secondary">
          Terms of Service
        </span>
        <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground">
          Terms & Conditions
        </h1>
        <p className="text-xs text-muted">
          Last Updated: November 2026 • Version 1.0
        </p>
      </div>

      <div className="space-y-6 text-sm text-foreground leading-relaxed">
        <section className="space-y-3">
          <h2 className="text-lg font-serif font-bold text-foreground">1. Acceptance of Terms</h2>
          <p className="text-muted">
            By accessing or using MetroScope, you agree to comply with and be bound by these Terms & Conditions. If you do not agree to these terms, please do not use the service.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-serif font-bold text-foreground">2. Nature of Service & News Discovery</h2>
          <p className="text-muted">
            MetroScope is an automated news discovery and aggregation platform that queries public news feeds, syndicated wire releases, and open news discovery indexes. MetroScope indexes public article metadata, headlines, publication times, and source references. MetroScope is not a primary publisher of third-party investigative works.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-serif font-bold text-foreground">3. Intellectual Property & Copyright</h2>
          <p className="text-muted">
            All original content, branding, logos, layout designs, and software code comprising MetroScope are the intellectual property of MetroScope. Third-party trademarks, news headlines, and article excerpts remain the property of their respective copyright holders. MetroScope respects intellectual property and promptly responds to valid DMCA or publisher removal requests submitted via our editorial desk.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-serif font-bold text-foreground">4. Limitation of Liability</h2>
          <p className="text-muted">
            The platform provides news discovery information on an &quot;as-is&quot; and &quot;as-available&quot; basis. MetroScope makes no representations or warranties regarding accuracy, completeness, or timeliness of external news stories indexed via automated algorithms.
          </p>
        </section>
      </div>
    </Container>
  );
}
