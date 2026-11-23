"use client";

import Link from "next/link";
import Image from "next/image";
import { useState } from "react";
import { Mail, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { Container } from "./Container";
import { NAVIGATION_CATEGORIES } from "./MainNavigation";
import { subscribeToNewsletter } from "@/lib/api";

export function SiteFooter() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionState, setSubmissionState] = useState<{
    status: "idle" | "verification_sent" | "already_subscribed" | "error";
    message: string;
  }>({ status: "idle", message: "" });

  const handleSubscribe = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail || isSubmitting) return;

    setIsSubmitting(true);
    setSubmissionState({ status: "idle", message: "" });

    try {
      const res = await subscribeToNewsletter(cleanEmail);
      if (res.success) {
        if (res.status === "already_subscribed") {
          setSubmissionState({
            status: "already_subscribed",
            message: res.message || "This email is already subscribed to MetroScope News.",
          });
        } else {
          setSubmissionState({
            status: "verification_sent",
            message: res.message || "Please check your inbox to confirm your subscription.",
          });
          setEmail("");
        }
      } else {
        setSubmissionState({
          status: "error",
          message: res.message || "Unable to process subscription. Please check your email and try again.",
        });
      }
    } catch {
      setSubmissionState({
        status: "error",
        message: "An unexpected network error occurred. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
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
              {submissionState.status === "verification_sent" ? (
                <div className="bg-secondary/20 border border-secondary p-5 rounded-lg text-center">
                  <CheckCircle className="w-8 h-8 text-secondary mx-auto mb-2" />
                  <p className="text-sm font-bold text-white">Check Your Inbox</p>
                  <p className="text-xs text-gray-200 mt-1">{submissionState.message}</p>
                  <button
                    onClick={() => setSubmissionState({ status: "idle", message: "" })}
                    className="mt-3 text-xs text-secondary hover:underline"
                  >
                    Subscribe another email
                  </button>
                </div>
              ) : submissionState.status === "already_subscribed" ? (
                <div className="bg-white/10 border border-white/20 p-5 rounded-lg text-center">
                  <CheckCircle className="w-8 h-8 text-secondary mx-auto mb-2" />
                  <p className="text-sm font-bold text-white">Already Subscribed</p>
                  <p className="text-xs text-gray-300 mt-1">{submissionState.message}</p>
                  <button
                    onClick={() => setSubmissionState({ status: "idle", message: "" })}
                    className="mt-3 text-xs text-secondary hover:underline"
                  >
                    Back to form
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubscribe} className="space-y-3">
                  <div className="flex flex-col sm:flex-row gap-2">
                    <div className="relative flex-1">
                      <input
                        type="email"
                        required
                        disabled={isSubmitting}
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Enter your email address"
                        className="w-full pl-9 pr-3 py-2.5 text-sm rounded bg-white/10 text-white placeholder:text-gray-400 border border-white/20 focus:outline-none focus:border-secondary disabled:opacity-50"
                      />
                      <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-3 pointer-events-none" />
                    </div>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="px-5 py-2.5 text-xs font-bold uppercase tracking-wider rounded bg-secondary text-white hover:bg-secondary/90 transition-colors whitespace-nowrap flex items-center justify-center gap-1.5 disabled:opacity-60"
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Sending...</span>
                        </>
                      ) : (
                        <span>Subscribe</span>
                      )}
                    </button>
                  </div>
                  {submissionState.status === "error" && (
                    <div className="flex items-center gap-1.5 text-xs text-red-400 bg-red-950/30 border border-red-800/40 px-3 py-2 rounded">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      <span>{submissionState.message}</span>
                    </div>
                  )}
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
            <Link href="/" className="inline-block bg-white/95 px-3 py-1.5 rounded-md">
              <Image
                src="/logo.png"
                alt="MetroScope"
                width={200}
                height={50}
                className="h-8 w-auto object-contain"
              />
            </Link>
            <p className="text-xs text-gray-300 leading-relaxed">
              MetroScope is a US-focused digital news publication presenting curated headlines, permitted summaries, and direct attribution to original reporting across national and international newsrooms.
            </p>
            <div className="text-[11px] text-gray-400">
              <span>National &amp; International Coverage</span>
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
            Original publisher copyrights acknowledged. Fair use news discovery and indexing service.
          </p>
        </div>
      </Container>
    </footer>
  );
}
