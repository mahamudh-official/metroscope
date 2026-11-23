import type { Metadata } from "next";
import { constructMetadata } from "@/lib/seo";

export const metadata: Metadata = constructMetadata({
  title: "Contact Editorial Desk — MetroScope",
  description: "Get in touch with the MetroScope editorial and technical news aggregation team.",
  canonicalUrl: "/contact",
});

export default function ContactLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
