"use client";

import Link from "next/link";
import Image from "next/image";
import { useState } from "react";
import { Mail, CheckCircle } from "lucide-react";
import { Container } from "./Container";
import { NAVIGATION_CATEGORIES } from "./MainNavigation";

export function SiteFooter() {
  const [email, setEmail] = useState("");
  const [subscribed, setSubscribed] = useState(false);

  const handleSubscribe = (e: React.FormEvent) => {
    e.preventDefault();
    if (email.trim()) {
      setSubscribed(true);
    }
  };

  return (
    <footer className="w-full bg-metro-navy text-white mt-16 border-t border-metro-navy/50">
      {/* Newsletter Subscription Section */}
      <section id="newsletter" className="border-b border-white/10 py-12">
        <Container>
          <div className="bg-white/5 rounded-lg p-6 md:p-8 backdrop-blur border border-white/10 grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
            <div>
              <span className="text-secondary text-xs uppercase font-bold tracking-widest">
                Daily News Dispatch
              </span>
              <h3 className="text-2xl md:text-3xl font-serif font-bold text-white mt-1">
                The Morning Scope & Evening Briefing
              </h3>
              <p className="text-gray-300 text-sm mt-2">
                Curated global news insights, technology breakthroughs, and market briefings delivered directly to your inbox.
              </p>
              <div className="flex items-center space-x-2 mt-4 text-xs text-gray-400">
                <CheckCircle className="w-3.5 h-3.5 text-secondary" />
                <span>Zero spam • Unsubscribe anytime</span>
              </div>
            </div>

            <div>
              {subscribed ? (
                <div className="bg-secondary/20 border border-secondary p-4 rounded text-center">
                  <CheckCircle className="w-6 h-6 text-secondary mx-auto mb-2" />
                  <p className="text-sm font-semibold text-white">Thank you for subscribing!</p>
                  <p className="text-xs text-gray-300 mt-1">You will receive the next edition of The Morning Scope.</p>
                </div>
              ) : (
                <form onSubmit={handleSubscribe} className="space-y-3">
                  <div className="flex flex-col sm:flex-row gap-2">
                    <div className="relative flex-1">
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Enter your email address"
                        className="w-full pl-9 pr-3 py-2.5 text-sm rounded bg-white/10 text-white placeholder:text-gray-400 border border-white/20 focus:outline-none focus:border-secondary"
                      />
                      <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-3 pointer-events-none" />
                    </div>
                    <button
                      type="submit"
                      className="px-5 py-2.5 text-xs font-bold uppercase tracking-wider rounded bg-secondary text-white hover:bg-secondary/90 transition-colors whitespace-nowrap"
                    >
                      Subscribe
                    </button>
                  </div>
                  <p className="text-[11px] text-gray-400">
                    By subscribing, you agree to our <Link href="/privacy" className="underline hover:text-white">Privacy Policy</Link> and <Link href="/terms" className="underline hover:text-white">Terms of Service</Link>.
                  </p>
                </form>
              )}
            </div>
          </div>
        </Container>
      </section>

      {/* Main Footer Links */}
      <Container className="py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand Info */}
          <div className="space-y-4 md:col-span-1">
            <Link href="/" className="inline-block">
              <Image
                src="/logo.png"
                alt="MetroScope"
                width={200}
                height={50}
                className="h-8 w-auto brightness-200"
              />
            </Link>
            <p className="text-xs text-gray-300 leading-relaxed">
              MetroScope is an automated, US-focused global news discovery platform. Delivering unbiased, verified intelligence powered by real-time GDELT data aggregation.
            </p>
            <div className="text-[11px] text-gray-400">
              <span>Primary Discovery: GDELT DOC 2.0 API</span>
            </div>
          </div>

          {/* Editorial Sections */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-widest text-secondary">
              News Desks
            </h4>
            <ul className="space-y-2 text-xs text-gray-300">
              {NAVIGATION_CATEGORIES.slice(1, 6).map((cat) => (
                <li key={cat.name}>
                  <Link href={cat.href} className="hover:text-white transition-colors">
                    {cat.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-widest text-secondary">
              Specialized Coverage
            </h4>
            <ul className="space-y-2 text-xs text-gray-300">
              {NAVIGATION_CATEGORIES.slice(6).map((cat) => (
                <li key={cat.name}>
                  <Link href={cat.href} className="hover:text-white transition-colors">
                    {cat.name}
                  </Link>
                </li>
              ))}
              <li>
                <Link href="/search" className="hover:text-white transition-colors">
                  Search Archive
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal & Company */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-widest text-secondary">
              Company & Legal
            </h4>
            <ul className="space-y-2 text-xs text-gray-300">
              <li>
                <Link href="/about" className="hover:text-white transition-colors">
                  About MetroScope
                </Link>
              </li>
              <li>
                <Link href="/contact" className="hover:text-white transition-colors">
                  Contact Editorial
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-white transition-colors">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="hover:text-white transition-colors">
                  Terms & Conditions
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom copyright & attribution */}
        <div className="border-t border-white/10 mt-12 pt-6 flex flex-col sm:flex-row items-center justify-between text-xs text-gray-400 gap-4">
          <p>© {new Date().getFullYear()} MetroScope News Network. All rights reserved.</p>
          <p className="text-[11px] text-gray-500">
            News discovery metadata indexed from GDELT Project. Original publisher copyrights acknowledged.
          </p>
        </div>
      </Container>
    </footer>
  );
}
