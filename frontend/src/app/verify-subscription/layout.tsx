import type { Metadata } from "next";
import { constructMetadata } from "@/lib/seo";

export const metadata: Metadata = constructMetadata({
  title: "Verify Subscription",
  description: "Confirm and activate your MetroScope Daily Briefing newsletter subscription.",
  canonicalUrl: "/verify-subscription",
  noIndex: true,
});

export default function VerifySubscriptionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
