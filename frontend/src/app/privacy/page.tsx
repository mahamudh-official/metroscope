import { Container } from "@/components/Container";
import { constructMetadata } from "@/lib/seo";
import Link from "next/link";

export const metadata = constructMetadata({
  title: "Privacy Policy",
  description: "MetroScope Privacy Policy regarding news discovery data, cookies, and user privacy rights.",
  canonicalUrl: "/privacy",
});

export default function PrivacyPage() {
  return (
    <Container className="py-12 max-w-4xl space-y-8">
      <div className="border-b border-border pb-6 space-y-2">
        <span className="text-xs font-bold uppercase tracking-widest text-secondary">
          Legal Compliance
        </span>
        <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground">
          Privacy Policy
        </h1>
        <p className="text-xs text-muted">
          Effective Date: November 2026 • Version 1.0
        </p>
      </div>

      <div className="space-y-6 text-sm text-foreground leading-relaxed">
        <section className="space-y-3">
          <h2 className="text-lg font-serif font-bold text-foreground">1. Introduction</h2>
          <p className="text-muted">
            MetroScope (&quot;we&quot;, &quot;our&quot;, or &quot;the Platform&quot;) operates a public news aggregation and discovery service. We are committed to transparency and honoring user privacy. We do not require account registration, reader profiling, or sell personal data.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-serif font-bold text-foreground">2. Information We Collect</h2>
          <p className="text-muted">
            Because MetroScope does not support reader accounts or public comments, data collection is strictly minimal:
          </p>
          <ul className="list-disc pl-5 space-y-1 text-muted text-xs">
            <li><strong>Technical Access Logs:</strong> Standard HTTP server logs including anonymized IP addresses, browser user agent strings, and request timestamps to maintain system availability and defend against DDoS attacks.</li>
            <li><strong>Email Newsletter:</strong> If you voluntarily subscribe to our news briefings, your email is stored securely solely for the purpose of dispatching scheduled editions. You can unsubscribe at any time.</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-serif font-bold text-foreground">3. Third-Party Publisher Links</h2>
          <p className="text-muted">
            MetroScope links to third-party news websites across the world. When you click an external link, you leave MetroScope and are subject to the privacy practices of that publishing entity. We encourage you to review their respective policies.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-serif font-bold text-foreground">4. Contact &amp; Privacy Requests</h2>
          <p className="text-muted">
            For privacy inquiries regarding subscriber data or email preference removal, readers may use the direct one-click unsubscribe link provided in every newsletter dispatch or visit our self-service <Link href="/unsubscribe" className="text-secondary underline font-semibold">Unsubscribe Portal</Link>. Inquiries regarding publisher exclusion or platform indexing may be directed via our <Link href="/contact" className="text-secondary underline font-semibold">Contact &amp; Attribution</Link> guidelines.
          </p>
        </section>
      </div>
    </Container>
  );
}
