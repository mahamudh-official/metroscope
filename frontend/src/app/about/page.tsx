import { Container } from "@/components/Container";
import { constructMetadata } from "@/lib/seo";
import { Shield, Globe, Newspaper, CheckCircle } from "lucide-react";

export const metadata = constructMetadata({
  title: "About MetroScope — Editorial Mission & Standards",
  description: "Learn about MetroScope's mission to present curated national and international news with clear publisher attribution.",
  canonicalUrl: "/about",
});

export default function AboutPage() {
  return (
    <Container className="py-12 max-w-4xl space-y-10">
      <div className="border-b border-border pb-6 space-y-2">
        <span className="text-xs font-bold uppercase tracking-widest text-secondary">
          Editorial Mission
        </span>
        <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground">
          About MetroScope
        </h1>
        <p className="text-base text-muted leading-relaxed font-sans">
          MetroScope is a US-focused digital news publication presenting curated headlines, permitted summaries, and direct links to original reporting across national and international newsrooms.
        </p>
      </div>

      <div className="space-y-6 text-foreground leading-relaxed text-sm">
        <h2 className="text-xl font-serif font-bold text-foreground">
          Our Editorial Principles
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
          <div className="border border-border p-5 rounded-lg bg-surface-lowest space-y-3">
            <Globe className="w-6 h-6 text-secondary" />
            <h3 className="font-bold text-base font-serif">Broad Coverage</h3>
            <p className="text-xs text-muted leading-relaxed">
              Following major developments across US affairs, world events, politics, business, technology, science, health, environment, sports, and culture.
            </p>
          </div>

          <div className="border border-border p-5 rounded-lg bg-surface-lowest space-y-3">
            <Newspaper className="w-6 h-6 text-secondary" />
            <h3 className="font-bold text-base font-serif">Editorial Clarity</h3>
            <p className="text-xs text-muted leading-relaxed">
              Organizing daily reporting into clear, readable broadsheet sections so readers can follow important stories without clutter or distraction.
            </p>
          </div>

          <div className="border border-border p-5 rounded-lg bg-surface-lowest space-y-3">
            <Shield className="w-6 h-6 text-secondary" />
            <h3 className="font-bold text-base font-serif">Source Attribution</h3>
            <p className="text-xs text-muted leading-relaxed">
              Crediting original news organizations and journalists prominently and linking readers directly to the primary publication for complete coverage.
            </p>
          </div>
        </div>

        <div className="space-y-4 pt-6 border-t border-border">
          <h2 className="text-xl font-serif font-bold text-foreground">
            Reader Experience &amp; Copyright Standards
          </h2>
          <p className="text-muted leading-relaxed">
            MetroScope is designed as an accessible public news reader. Rather than reproducing full third-party articles, we present headlines, publication metadata, and concise permitted summaries while directing readers to the original publisher&apos;s website.
          </p>
          <ul className="space-y-2 pt-2 text-xs text-muted">
            <li className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-secondary shrink-0" />
              <span>Direct canonical links and clear attribution for every featured story</span>
            </li>
            <li className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-secondary shrink-0" />
              <span>Open public access without mandatory reader accounts or paywalls</span>
            </li>
            <li className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-secondary shrink-0" />
              <span>Readable broadsheet typography across desktop and mobile devices in light and dark modes</span>
            </li>
          </ul>
        </div>
      </div>
    </Container>
  );
}
