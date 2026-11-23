"use client";

import React, { useState } from "react";
import Image from "next/image";
import { Camera } from "lucide-react";

interface ArticleHeroImageProps {
  src?: string | null;
  alt: string;
  sourceName: string;
  caption?: string | null;
  credit?: string | null;
  categoryName?: string | null;
}

export function ArticleHeroImage({
  src,
  alt,
  sourceName,
  caption,
  credit,
  categoryName,
}: ArticleHeroImageProps) {
  const [hasError, setHasError] = useState(false);

  // Validate URL scheme client-side and hide on load error
  if (!src || hasError) {
    return null;
  }

  const cleanSrc = src.trim();
  if (!cleanSrc.startsWith("http://") && !cleanSrc.startsWith("https://")) {
    return null;
  }

  const displayCredit = credit || (sourceName ? `Photo via ${sourceName}` : null);

  return (
    <figure className="my-6 space-y-2">
      <div className="relative aspect-[16/9] w-full overflow-hidden rounded-xl border border-border bg-surface-lowest shadow-sm">
        <Image
          src={cleanSrc}
          alt={alt}
          fill
          priority
          sizes="(max-width: 768px) 100vw, (max-width: 1200px) 85vw, 896px"
          className="object-cover transition-opacity duration-300"
          unoptimized
          referrerPolicy="no-referrer"
          onError={() => setHasError(true)}
        />
        {categoryName && (
          <div className="absolute top-3 left-3 px-2.5 py-1 bg-primary/85 backdrop-blur-sm text-white text-[11px] font-bold uppercase rounded tracking-wider shadow">
            {categoryName}
          </div>
        )}
      </div>
      {(caption || displayCredit) && (
        <figcaption className="text-xs text-muted leading-relaxed flex flex-col sm:flex-row sm:items-center justify-between gap-x-4 gap-y-1 px-1">
          {caption ? (
            <span className="font-sans text-foreground/85">{caption}</span>
          ) : (
            <span />
          )}
          {displayCredit && (
            <span className="inline-flex items-center space-x-1 text-[11px] font-sans text-muted shrink-0 italic">
              <Camera className="w-3 h-3 text-secondary inline-block shrink-0" />
              <span>{displayCredit}</span>
            </span>
          )}
        </figcaption>
      )}
    </figure>
  );
}
