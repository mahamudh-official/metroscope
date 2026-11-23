"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, Loader2, ArrowLeft } from "lucide-react";
import { Container } from "@/components/Container";
import { unsubscribeFromNewsletter } from "@/lib/api";

function UnsubscribeContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [state, setState] = useState<{
    isLoading: boolean;
    isSuccess: boolean;
    message: string;
  }>({
    isLoading: true,
    isSuccess: false,
    message: "Processing your unsubscribe request...",
  });

  useEffect(() => {
    if (!token) {
      setState({
        isLoading: false,
        isSuccess: false,
        message: "No unsubscribe token provided. Please use the unsubscribe link from your newsletter email.",
      });
      return;
    }

    let isMounted = true;
    unsubscribeFromNewsletter(token)
      .then((res) => {
        if (!isMounted) return;
        if (res.success) {
          setState({
            isLoading: false,
            isSuccess: true,
            message: res.message || "You have been unsubscribed from the MetroScope newsletter.",
          });
        } else {
          setState({
            isLoading: false,
            isSuccess: false,
            message: res.message || "Unable to process unsubscription. The link may be invalid.",
          });
        }
      })
      .catch(() => {
        if (!isMounted) return;
        setState({
          isLoading: false,
          isSuccess: false,
          message: "Unable to connect to unsubscription service. Please try again later.",
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
              <h1 className="text-xl font-bold text-foreground font-serif">Updating Subscription</h1>
              <p className="text-sm text-muted">{state.message}</p>
            </div>
          ) : state.isSuccess ? (
            <div className="py-4 space-y-4">
              <CheckCircle2 className="w-16 h-16 text-emerald-600 mx-auto" />
              <h1 className="text-2xl font-bold text-foreground font-serif">Unsubscribed</h1>
              <p className="text-sm text-muted leading-relaxed">{state.message}</p>
              <p className="text-xs text-muted">
                You will no longer receive newsletter briefings from MetroScope.
              </p>
              <div className="pt-4 flex flex-col sm:flex-row gap-3 justify-center">
                <Link
                  href="/"
                  className="inline-flex items-center justify-center gap-1.5 px-5 py-2.5 rounded-lg border border-border text-foreground text-sm font-medium hover:bg-surface-container transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>Return to Home</span>
                </Link>
                <Link
                  href="/#newsletter"
                  className="inline-flex items-center justify-center px-5 py-2.5 rounded-lg bg-secondary text-white text-sm font-semibold hover:bg-secondary/90 transition-colors"
                >
                  <span>Re-subscribe</span>
                </Link>
              </div>
            </div>
          ) : (
            <div className="py-4 space-y-4">
              <AlertTriangle className="w-16 h-16 text-amber-500 mx-auto" />
              <h1 className="text-2xl font-bold text-foreground font-serif">Unsubscribe Status</h1>
              <p className="text-sm text-muted leading-relaxed">{state.message}</p>
              <div className="pt-4">
                <Link
                  href="/"
                  className="inline-flex items-center justify-center gap-1.5 px-6 py-3 rounded-lg bg-secondary text-white text-sm font-semibold hover:bg-secondary/90 transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>Return to Homepage</span>
                </Link>
              </div>
            </div>
          )}
        </div>
      </Container>
    </div>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense
      fallback={
        <div className="py-20">
          <Container>
            <div className="max-w-md mx-auto p-8 text-center">
              <Loader2 className="w-8 h-8 text-secondary animate-spin mx-auto mb-2" />
              <p className="text-sm text-muted">Loading unsubscription details...</p>
            </div>
          </Container>
        </div>
      }
    >
      <UnsubscribeContent />
    </Suspense>
  );
}
