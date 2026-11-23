import { Container } from "@/components/Container";
import { constructMetadata } from "@/lib/seo";
import { Newspaper, Building2, MailCheck, ShieldCheck, ArrowRight } from "lucide-react";
import Link from "next/link";

export const metadata = constructMetadata({
  title: "Contact & Editorial Inquiries",
  description: "Contact information, publisher attribution guidance, and platform communications for MetroScope.",
  canonicalUrl: "/contact",
});

export default function ContactPage() {
  return (
    <Container className="py-12 max-w-4xl space-y-10">
      <div className="border-b border-border pb-6 space-y-2">
        <span className="text-xs font-bold uppercase tracking-widest text-secondary">
          Platform Guidance &amp; Inquiries
        </span>
        <h1 className="text-3xl md:text-4xl font-serif font-bold text-foreground">
          Contact MetroScope
        </h1>
        <p className="text-base text-muted leading-relaxed font-sans">
          MetroScope is an automated news discovery engine that indexes public wire coverage and syndicate reporting. Review the guidance below to direct inquiries to the appropriate desk.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Story Inquiries & Corrections */}
        <div className="border border-border rounded-lg p-6 bg-surface-lowest space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-secondary">
              <Newspaper className="w-5 h-5" />
              <h2 className="text-base font-serif font-bold text-foreground">
                Story Inquiries &amp; Corrections
              </h2>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              MetroScope does not write, edit, or commission original news articles. All stories indexed on this platform originate from third-party publishers and public wire services.
            </p>
            <p className="text-xs text-muted leading-relaxed">
              To request a correction, submit editorial feedback, or report factual errors in a specific news story, please contact the primary reporting outlet credited on that article&apos;s detail page directly.
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center space-x-1.5 text-xs font-semibold text-secondary hover:underline pt-2"
          >
            <span>Return to Headlines</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Publisher Attribution & Indexing */}
        <div className="border border-border rounded-lg p-6 bg-surface-lowest space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-secondary">
              <Building2 className="w-5 h-5" />
              <h2 className="text-base font-serif font-bold text-foreground">
                Publisher Attribution &amp; Licensing
              </h2>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              MetroScope honors publisher copyright, fair-use indexation standards, and canonical link attribution. We provide direct canonical links to the original publisher for every indexed dispatch.
            </p>
            <p className="text-xs text-muted leading-relaxed">
              Publishers seeking to update organization display names, verify domain categorization, or request crawler exclusion under automated syndication guidelines may review our terms and platform policies.
            </p>
          </div>
          <Link
            href="/terms"
            className="inline-flex items-center space-x-1.5 text-xs font-semibold text-secondary hover:underline pt-2"
          >
            <span>Review Terms &amp; Policies</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Newsletter & Subscriptions */}
        <div className="border border-border rounded-lg p-6 bg-surface-lowest space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-secondary">
              <MailCheck className="w-5 h-5" />
              <h2 className="text-base font-serif font-bold text-foreground">
                Newsletter &amp; Email Delivery
              </h2>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              MetroScope operates an automated double opt-in newsletter for verified subscribers. Readers can manage email subscription preferences or withdraw consent at any time without creating an account.
            </p>
            <p className="text-xs text-muted leading-relaxed">
              Every dispatched edition contains a single-click unsubscribe link. You may also cancel your active subscription immediately using our self-service portal.
            </p>
          </div>
          <Link
            href="/unsubscribe"
            className="inline-flex items-center space-x-1.5 text-xs font-semibold text-secondary hover:underline pt-2"
          >
            <span>Manage Subscription</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Operations Notice */}
        <div className="border border-border rounded-lg p-6 bg-surface-lowest space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-secondary">
              <ShieldCheck className="w-5 h-5" />
              <h2 className="text-base font-serif font-bold text-foreground">
                Platform Operations Notice
              </h2>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              MetroScope&apos;s domain dispatches automated outbound notifications for subscriber newsletters. Dedicated inbound departmental mailboxes are currently reserved while production mail-exchange routing is finalized.
            </p>
            <p className="text-xs text-muted leading-relaxed">
              For technical inquiries, open platform maintenance, or administrative notices, please consult the official project documentation and administration channels.
            </p>
          </div>
          <Link
            href="/about"
            className="inline-flex items-center space-x-1.5 text-xs font-semibold text-secondary hover:underline pt-2"
          >
            <span>Learn About the Platform</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </Container>
  );
}
