"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CheckCircle2, XCircle, Loader2, ArrowRight } from "lucide-react";
import { Container } from "@/components/Container";
import { verifyNewsletterSubscription } from "@/lib/api";

function VerifySubscriptionContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [state, setState] = useState<{
    isLoading: boolean;
    isSuccess: boolean;
    message: string;
  }>({
    isLoading: true,
    isSuccess: false,
    message: "Verifying your subscription...",
  });

  useEffect(() => {
    if (!token) {
      setState({
        isLoading: false,
        isSuccess: false,
        message: "No verification token provided. Please check the link in your email.",
      });
      return;
    }

    let isMounted = true;
    verifyNewsletterSubscription(token)
      .then((res) => {
        if (!isMounted) return;
        if (res.success) {
          setState({
            isLoading: false,
            isSuccess: true,
            message: res.message || "Your subscription has been verified successfully!",
          });
        } else {
          setState({
            isLoading: false,
            isSuccess: false,
            message: res.message || "Verification failed. The link may have expired or is invalid.",
          });
        }
      })
      .catch(() => {
        if (!isMounted) return;
        setState({
          isLoading: false,
          isSuccess: false,
          message: "Unable to connect to verification service. Please try again later.",
        });
      });

    return () => {
      isMounted = false;
    };
  }, [token]);

  return (
    <div className="py-20">
      <Container>
        <div className="max-w-md mx-auto bg-surface-lowest rounded-xl shadow-sm border border-border p-8 text-center">
          {state.isLoading ? (
            <div className="py-8 space-y-4">
              <Loader2 className="w-12 h-12 text-secondary animate-spin mx-auto" />
              <h1 className="text-xl font-bold text-foreground font-serif">Verifying Subscription</h1>
              <p className="text-sm text-muted">{state.message}</p>
            </div>
          ) : state.isSuccess ? (
            <div className="py-4 space-y-4">
              <CheckCircle2 className="w-16 h-16 text-emerald-600 mx-auto" />
              <h1 className="text-2xl font-bold text-foreground font-serif">Subscription Confirmed!</h1>
              <p className="text-sm text-muted leading-relaxed">{state.message}</p>
              <div className="pt-4">
                <Link
                  href="/"
                  className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-secondary text-white text-sm font-semibold hover:bg-secondary/90 transition-colors"
                >
                  <span>Explore Today&apos;s News</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          ) : (
            <div className="py-4 space-y-4">
              <XCircle className="w-16 h-16 text-red-500 mx-auto" />
              <h1 className="text-2xl font-bold text-foreground font-serif">Verification Issue</h1>
              <p className="text-sm text-muted leading-relaxed">{state.message}</p>
              <div className="pt-4">
                <Link
                  href="/#newsletter"
                  className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-secondary text-white text-sm font-semibold hover:bg-secondary/90 transition-colors"
                >
                  <span>Request a New Link</span>
                </Link>
              </div>
            </div>
          )}
        </div>
      </Container>
    </div>
  );
}

export default function VerifySubscriptionPage() {
  return (
    <Suspense
      fallback={
        <div className="py-20">
          <Container>
            <div className="max-w-md mx-auto p-8 text-center">
              <Loader2 className="w-8 h-8 text-secondary animate-spin mx-auto mb-2" />
              <p className="text-sm text-muted">Loading verification details...</p>
            </div>
          </Container>
        </div>
      }
    >
      <VerifySubscriptionContent />
    </Suspense>
  );
}
