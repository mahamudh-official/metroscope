"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export const NAVIGATION_CATEGORIES = [
  { name: "Home", slug: "", href: "/" },
  { name: "US", slug: "us", href: "/category/us" },
  { name: "World", slug: "world", href: "/category/world" },
  { name: "Politics", slug: "politics", href: "/category/politics" },
  { name: "Business", slug: "business", href: "/category/business" },
  { name: "Technology", slug: "technology", href: "/category/technology" },
  { name: "Science", slug: "science", href: "/category/science" },
  { name: "Health", slug: "health", href: "/category/health" },
  { name: "Environment", slug: "environment", href: "/category/environment" },
  { name: "Sports", slug: "sports", href: "/category/sports" },
  { name: "Entertainment", slug: "entertainment", href: "/category/entertainment" },
];

export function MainNavigation({ className }: { className?: string }) {
  const pathname = usePathname();

  return (
    <nav
      className={cn(
        "flex items-center space-x-1 md:space-x-4 overflow-x-auto py-2.5 scrollbar-none",
        className
      )}
      aria-label="Main Navigation"
    >
      {NAVIGATION_CATEGORIES.map((cat) => {
        const isActive =
          cat.href === "/"
            ? pathname === "/"
            : pathname.startsWith(cat.href);

        return (
          <Link
            key={cat.name}
            href={cat.href}
            className={cn(
              "px-2.5 py-1 text-xs md:text-sm font-semibold uppercase tracking-wider transition-colors whitespace-nowrap",
              isActive
                ? "text-secondary font-bold border-b-2 border-secondary"
                : "text-muted hover:text-foreground"
            )}
            aria-current={isActive ? "page" : undefined}
          >
            {cat.name}
          </Link>
        );
      })}
    </nav>
  );
}
