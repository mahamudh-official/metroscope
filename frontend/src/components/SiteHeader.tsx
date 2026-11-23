"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Search, Menu, X } from "lucide-react";
import { Container } from "./Container";
import { MainNavigation, NAVIGATION_CATEGORIES } from "./MainNavigation";
import { ThemeToggle } from "./ThemeToggle";

export function SiteHeader() {
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const today = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(new Date());

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setMobileMenuOpen(false);
    }
  };

  return (
    <header className="w-full bg-surface-lowest text-foreground border-b border-border">
      {/* Top utility bar */}
      <div className="w-full bg-surface-low border-b border-border py-1.5 text-xs text-muted">
        <Container className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <span className="font-medium">{today}</span>
            <span className="hidden sm:inline-block text-border">|</span>
            <span className="hidden sm:inline-block font-semibold uppercase tracking-wider text-secondary">
              US Edition
            </span>
          </div>
          <div className="flex items-center space-x-3">
            <Link
              href="#newsletter"
              className="hidden md:inline-flex items-center text-xs font-semibold uppercase tracking-wider text-secondary hover:underline"
            >
              Newsletters
            </Link>
            <ThemeToggle />
          </div>
        </Container>
      </div>

      {/* Main Masthead Banner */}
      <Container className="py-4 md:py-6">
        <div className="grid grid-cols-3 items-center">
          {/* Left: Mobile menu button & quick search on desktop */}
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded border border-border text-foreground hover:bg-surface-container"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            <form
              onSubmit={handleSearchSubmit}
              className="hidden lg:flex items-center relative w-64"
            >
              <input
                type="text"
                placeholder="Search news, topics..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded border border-border bg-surface text-foreground placeholder:text-muted focus:outline-none focus:border-secondary transition-colors"
              />
              <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 pointer-events-none" />
            </form>
          </div>

          {/* Center: MetroScope Official Logo */}
          <div className="flex flex-col items-center justify-center text-center">
            <Link
              href="/"
              className="inline-block dark:bg-white/95 dark:px-3.5 dark:py-1.5 dark:rounded-md transition-colors"
              aria-label="MetroScope Home"
            >
              <Image
                src="/logo.png"
                alt="MetroScope"
                width={260}
                height={60}
                priority
                className="h-9 md:h-12 w-auto object-contain"
              />
            </Link>
            <span className="text-[10px] md:text-xs uppercase tracking-widest text-muted mt-1.5 font-serif hidden sm:block">
              National &amp; International News
            </span>
          </div>

          {/* Right: Quick Search button for mobile / Subscribe button */}
          <div className="flex items-center justify-end space-x-3">
            <Link
              href="/search"
              className="lg:hidden p-2 text-foreground hover:text-secondary"
              aria-label="Search"
            >
              <Search className="w-5 h-5" />
            </Link>
            <Link
              href="#newsletter"
              className="hidden sm:inline-flex items-center px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider rounded bg-secondary text-white hover:bg-secondary/90 transition-colors"
            >
              Subscribe
            </Link>
          </div>
        </div>
      </Container>

      {/* Editorial Sub-bar */}
      <div className="w-full bg-metro-navy text-white text-xs py-1.5 overflow-hidden border-y border-metro-navy">
        <Container className="flex items-center space-x-3">
          <div className="flex items-center shrink-0 bg-secondary px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider text-white">
            <span>Latest Coverage</span>
          </div>
          <div className="truncate text-gray-200">
            <span>Reporting and summaries from leading national and international newsrooms</span>
          </div>
        </Container>
      </div>

      {/* Main Navigation (Desktop) */}
      <div className="w-full border-t border-border bg-surface-lowest hidden lg:block">
        <Container>
          <MainNavigation />
        </Container>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden w-full border-t border-border bg-surface-lowest px-4 py-4 space-y-4">
          <form onSubmit={handleSearchSubmit} className="flex items-center relative w-full">
            <input
              type="text"
              placeholder="Search news, topics..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm rounded border border-border bg-surface text-foreground placeholder:text-muted focus:outline-none focus:border-secondary"
            />
            <Search className="w-4 h-4 text-muted absolute left-3 pointer-events-none" />
          </form>

          <div className="flex flex-col space-y-2 border-t border-border pt-3">
            <span className="text-xs font-bold uppercase tracking-wider text-muted">
              Sections
            </span>
            <div className="grid grid-cols-2 gap-2">
              {NAVIGATION_CATEGORIES.map((item) => (
                <Link
                  key={item.name}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="py-1 text-sm font-medium text-foreground hover:text-secondary"
                >
                  {item.name}
                </Link>
              ))}
            </div>
          </div>

          <div className="border-t border-border pt-3 flex flex-col space-y-2 text-xs text-muted">
            <Link href="/about" onClick={() => setMobileMenuOpen(false)}>About Us</Link>
            <Link href="/contact" onClick={() => setMobileMenuOpen(false)}>Contact</Link>
            <Link href="/privacy" onClick={() => setMobileMenuOpen(false)}>Privacy Policy</Link>
            <Link href="/terms" onClick={() => setMobileMenuOpen(false)}>Terms & Conditions</Link>
          </div>
        </div>
      )}
    </header>
  );
}
