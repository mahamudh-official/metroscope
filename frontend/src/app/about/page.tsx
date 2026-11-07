import { Container } from "@/components/Container";
import { constructMetadata } from "@/lib/seo";
import { Shield, Globe, Cpu, CheckCircle } from "lucide-react";

export const metadata = constructMetadata({
  title: "About Us — Editorial Mission & Discovery Engine",
  description: "Learn about MetroScope's mission to deliver unbiased, automated news discovery and aggregation.",
});

export default function AboutPage() {
  return (
    <Container className="py-12 max-w-4xl space-y-10">
      <div className="border-b border-border pb-6 space-y-2">
        <span className="text-xs font-bold uppercase tracking-widest text-secondary">
          Platform Mission
        </span>
        <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground">
          About MetroScope
        </h1>
        <p className="text-base text-muted leading-relaxed font-sans">
          MetroScope is an automated, US-focused global news aggregation and distribution platform built for clarity, objectivity, and broadsheet editorial poise.
        </p>
      </div>

      <div className="space-y-6 text-foreground leading-relaxed text-sm">
        <h2 className="text-xl font-serif font-bold text-foreground">
          Our Architectural Principles
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
          <div className="border border-border p-5 rounded-lg bg-surface-lowest space-y-3">
            <Globe className="w-6 h-6 text-secondary" />
            <h3 className="font-bold text-base font-serif">Global Discovery</h3>
            <p className="text-xs text-muted leading-relaxed">
              Continuously indexing millions of worldwide news signals via GDELT DOC 2.0 to identify emerging stories without platform bias.
            </p>
          </div>

          <div className="border border-border p-5 rounded-lg bg-surface-lowest space-y-3">
            <Cpu className="w-6 h-6 text-secondary" />
            <h3 className="font-bold text-base font-serif">Automated Normalization</h3>
            <p className="text-xs text-muted leading-relaxed">
              Standardizing metadata, eliminating duplications, and classifying news items into structured editorial domains.
            </p>
          </div>

          <div className="border border-border p-5 rounded-lg bg-surface-lowest space-y-3">
            <Shield className="w-6 h-6 text-secondary" />
            <h3 className="font-bold text-base font-serif">Publisher Copyright</h3>
            <p className="text-xs text-muted leading-relaxed">
              Prominently crediting original journalism entities, preserving external source attribution, and directing readers to primary reporting.
            </p>
          </div>
        </div>

        <div className="space-y-4 pt-6 border-t border-border">
          <h2 className="text-xl font-serif font-bold text-foreground">
            Technology Infrastructure
          </h2>
          <p className="text-muted leading-relaxed">
            MetroScope is engineered as a resource-efficient modular monolith designed to operate smoothly within memory-constrained environments (2 vCPU, 2 GB RAM). Built with FastAPI, PostgreSQL, Next.js, and APScheduler, the platform prioritizes rapid delivery, SEO optimization, and high availability.
          </p>
          <ul className="space-y-2 pt-2 text-xs text-muted">
            <li className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-secondary" />
              <span>Full compliance with GDELT API data usage terms</span>
            </li>
            <li className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-secondary" />
              <span>Pure public news discovery — zero accounts, paywalls, or invasive profiling</span>
            </li>
            <li className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-secondary" />
              <span>Disciplined broadsheet typography and fast light/dark themes</span>
            </li>
          </ul>
        </div>
      </div>
    </Container>
  );
}
