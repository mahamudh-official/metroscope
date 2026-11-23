import type { Metadata } from "next";
import { constructMetadata } from "@/lib/seo";

export const metadata: Metadata = constructMetadata({
  title: "Unsubscribe from Newsletter",
  description: "Manage your email preferences and unsubscribe from the MetroScope newsletter.",
  canonicalUrl: "/unsubscribe",
  noIndex: true,
});

export default function UnsubscribeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
