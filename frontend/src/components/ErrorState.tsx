"use client";

import Link from "next/link";
import { AlertCircle, RotateCcw, Home } from "lucide-react";
import { Container } from "./Container";

interface ErrorStateProps {
  title?: string;
  message?: string;
  retry?: () => void;
}

export function ErrorState({
  title = "Unable to load content",
  message = "A technical disruption occurred while loading news records. Please try again or return to the homepage.",
  retry,
}: ErrorStateProps) {
  return (
    <Container className="py-20">
      <div className="max-w-md mx-auto text-center border border-border bg-surface-lowest p-8 rounded-lg shadow-sm">
        <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 flex items-center justify-center mx-auto mb-4">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-serif font-bold text-foreground mb-2">{title}</h2>
        <p className="text-xs text-muted mb-6 leading-relaxed">{message}</p>
        <div className="flex items-center justify-center space-x-3">
          {retry && (
            <button
              onClick={retry}
              type="button"
              className="inline-flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold uppercase tracking-wider rounded border border-border hover:bg-surface-container transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          )}
          <Link
            href="/"
            className="inline-flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold uppercase tracking-wider rounded bg-metro-navy dark:bg-primary-container text-white hover:opacity-90 transition-opacity"
          >
            <Home className="w-3.5 h-3.5" />
            <span>Return Home</span>
          </Link>
        </div>
      </div>
    </Container>
  );
}
