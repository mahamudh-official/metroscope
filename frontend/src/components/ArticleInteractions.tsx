"use client";

import React, { useState, useEffect } from "react";
import {
  Volume2,
  VolumeX,
  Bookmark,
  BookmarkCheck,
  Share2,
  Link as LinkIcon,
  Check,
  Printer,
  Play,
  Pause,
} from "lucide-react";

interface ArticleInteractionsProps {
  title: string;
  readingTimeMinutes?: number;
}

export function ArticleInteractions({
  title,
  readingTimeMinutes = 5,
}: ArticleInteractionsProps) {
  const [scrollProgress, setScrollProgress] = useState(0);
  const [isBookmarked, setIsBookmarked] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [fontSizeClass, setFontSizeClass] = useState<"normal" | "sm" | "lg">("normal");

  useEffect(() => {
    const handleScroll = () => {
      const winScroll = document.documentElement.scrollTop || document.body.scrollTop;
      const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      if (height > 0) {
        setScrollProgress(Math.min(100, Math.max(0, (winScroll / height) * 100)));
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleCopyLink = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handlePrint = () => {
    if (typeof window !== "undefined") {
      window.print();
    }
  };

  const handleShareX = () => {
    if (typeof window !== "undefined") {
      const shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(
        title
      )}&url=${encodeURIComponent(window.location.href)}`;
      window.open(shareUrl, "_blank", "noopener,noreferrer");
    }
  };

  const handleShareFacebook = () => {
    if (typeof window !== "undefined") {
      const shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(
        window.location.href
      )}`;
      window.open(shareUrl, "_blank", "noopener,noreferrer");
    }
  };

  const setFontSize = (size: "sm" | "normal" | "lg") => {
    setFontSizeClass(size);
    const contentEl = document.getElementById("article-content");
    if (contentEl) {
      contentEl.classList.remove("text-base", "text-lg", "text-xl");
      if (size === "sm") {
        contentEl.classList.add("text-base");
      } else if (size === "lg") {
        contentEl.classList.add("text-xl");
      } else {
        contentEl.classList.add("text-lg");
      }
    }
  };

  return (
    <>
      {/* Top Sticky Reading Progress Bar */}
      <div
        className="sticky top-0 z-40 w-full h-1 bg-surface-container"
        id="scroll-progress-container"
        aria-hidden="true"
      >
        <div
          className="h-full bg-secondary transition-all duration-150 ease-out"
          id="scroll-progress"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>

      {/* Utility & Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 py-2 px-3 sm:px-4 bg-surface-lowest rounded-lg shadow-sm border border-border">
        {/* Audio Narration Bar */}
        <div className="flex items-center gap-2 bg-surface-low px-3 py-1.5 rounded-lg flex-1 sm:flex-initial">
          <button
            type="button"
            aria-label={isPlayingAudio ? "Pause story audio" : "Listen to story audio"}
            onClick={() => setIsPlayingAudio(!isPlayingAudio)}
            className="w-7 h-7 rounded-full bg-primary text-on-primary flex items-center justify-center hover:bg-primary-container transition-colors"
          >
            {isPlayingAudio ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
          </button>
          <div className="flex flex-col">
            <span className="text-[11px] font-bold uppercase tracking-wider text-foreground">
              {isPlayingAudio ? "Playing Story" : "Listen to story"}
            </span>
            <span className="text-[10px] text-muted">
              {readingTimeMinutes}:00 min • Audio Dispatch
            </span>
          </div>
        </div>

        {/* Social Sharing & Typography Sizer */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Bookmark Button */}
          <button
            type="button"
            aria-label="Bookmark article"
            onClick={() => setIsBookmarked(!isBookmarked)}
            className={`p-1.5 rounded hover:bg-surface-container transition-colors ${
              isBookmarked ? "text-secondary" : "text-muted hover:text-foreground"
            }`}
            title={isBookmarked ? "Story saved" : "Save story"}
          >
            {isBookmarked ? (
              <BookmarkCheck className="w-4 h-4 text-secondary" />
            ) : (
              <Bookmark className="w-4 h-4" />
            )}
          </button>

          <div className="h-4 w-px bg-border hidden sm:block" />

          {/* Share on X */}
          <button
            type="button"
            aria-label="Share on X"
            onClick={handleShareX}
            className="p-1.5 rounded text-muted hover:text-foreground hover:bg-surface-container transition-colors"
            title="Share on X"
          >
            <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
            </svg>
          </button>

          {/* Share on Facebook */}
          <button
            type="button"
            aria-label="Share on Facebook"
            onClick={handleShareFacebook}
            className="p-1.5 rounded text-muted hover:text-foreground hover:bg-surface-container transition-colors"
            title="Share on Facebook"
          >
            <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
              <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
            </svg>
          </button>

          {/* Copy Link Button */}
          <button
            type="button"
            aria-label="Copy article link"
            onClick={handleCopyLink}
            className={`p-1.5 rounded hover:bg-surface-container transition-colors flex items-center gap-1 ${
              copied ? "text-secondary font-bold" : "text-muted hover:text-foreground"
            }`}
            title="Copy Link"
          >
            {copied ? <Check className="w-4 h-4 text-secondary" /> : <LinkIcon className="w-4 h-4" />}
          </button>

          {/* Print Button */}
          <button
            type="button"
            aria-label="Print article"
            onClick={handlePrint}
            className="p-1.5 rounded text-muted hover:text-foreground hover:bg-surface-container transition-colors hidden sm:block"
            title="Print Article"
          >
            <Printer className="w-4 h-4" />
          </button>

          <div className="h-4 w-px bg-border" />

          {/* Typography Sizer (A- / A / A+) */}
          <div className="flex items-center bg-surface-low rounded p-0.5">
            <button
              type="button"
              onClick={() => setFontSize("sm")}
              className={`px-1.5 py-0.5 text-xs font-semibold rounded ${
                fontSizeClass === "sm" ? "bg-surface-lowest text-foreground shadow-xs" : "text-muted hover:text-foreground"
              }`}
              title="Smaller font"
            >
              A-
            </button>
            <button
              type="button"
              onClick={() => setFontSize("normal")}
              className={`px-1.5 py-0.5 text-xs font-bold rounded ${
                fontSizeClass === "normal" ? "bg-surface-lowest text-foreground shadow-xs" : "text-muted hover:text-foreground"
              }`}
              title="Default font"
            >
              A
            </button>
            <button
              type="button"
              onClick={() => setFontSize("lg")}
              className={`px-1.5 py-0.5 text-xs font-semibold rounded ${
                fontSizeClass === "lg" ? "bg-surface-lowest text-foreground shadow-xs" : "text-muted hover:text-foreground"
              }`}
              title="Larger font"
            >
              A+
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
