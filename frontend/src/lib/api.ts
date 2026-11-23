export interface NewsSource {
  id: number;
  name: string;
  domain: string;
  website_url?: string | null;
  country?: string | null;
  language?: string | null;
}

export interface NewsCategory {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  article_count?: number;
}

export interface ArticleListItem {
  id: number;
  title: string;
  slug: string;
  description?: string | null;
  canonical_url: string;
  image_url?: string | null;
  author?: string | null;
  publisher_name?: string | null;
  language: string;
  country?: string | null;
  published_at?: string | null;
  is_trending?: boolean;
  is_breaking?: boolean;
  source?: NewsSource | null;
  category?: NewsCategory | null;
}

export interface ArticleInlineImage {
  url: string;
  caption?: string | null;
  credit?: string | null;
  authorized?: boolean;
}

export interface ArticleDetail extends ArticleListItem {
  full_text?: string | null;
  content_display_authorized?: boolean;
  updated_at?: string | null;
  image_caption?: string | null;
  image_credit?: string | null;
  inline_images?: ArticleInlineImage[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  error?: boolean;
}

const getApiBaseUrl = (): string => {
  // During server-side render or build in Node.js
  if (typeof window === "undefined") {
    return (
      process.env.INTERNAL_API_URL?.replace(/\/$/, "") ||
      process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
      "http://127.0.0.1:8000/api/v1"
    );
  }
  // In the browser client
  return process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "/api/v1";
};

export async function fetchArticles(params?: {
  page?: number;
  pageSize?: number;
  category?: string;
  q?: string;
  trending?: boolean;
  breaking?: boolean;
}): Promise<PaginatedResponse<ArticleListItem>> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", params.page.toString());
  if (params?.pageSize) query.set("page_size", params.pageSize.toString());
  if (params?.category) query.set("category", params.category);
  if (params?.q) query.set("q", params.q);
  if (params?.trending !== undefined) query.set("trending", params.trending.toString());
  if (params?.breaking !== undefined) query.set("breaking", params.breaking.toString());

  const qs = query.toString();
  const url = `${getApiBaseUrl()}/articles${qs ? `?${qs}` : ""}`;

  try {
    const res = await fetch(url, {
      next: { revalidate: 60 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      return { items: [], total: 0, page: 1, page_size: params?.pageSize || 20, total_pages: 0, error: true };
    }
    return await res.json();
  } catch {
    return { items: [], total: 0, page: 1, page_size: params?.pageSize || 20, total_pages: 0, error: true };
  }
}

export async function fetchArticleBySlug(slug: string): Promise<ArticleDetail | null> {
  const url = `${getApiBaseUrl()}/articles/${encodeURIComponent(slug)}`;
  try {
    const res = await fetch(url, {
      next: { revalidate: 60 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      return null;
    }
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchRelatedArticles(
  slug: string,
  limit: number = 4
): Promise<ArticleListItem[]> {
  const url = `${getApiBaseUrl()}/articles/${encodeURIComponent(slug)}/related?limit=${limit}`;
  try {
    const res = await fetch(url, {
      next: { revalidate: 60 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      return [];
    }
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchCategories(): Promise<NewsCategory[]> {
  const url = `${getApiBaseUrl()}/categories`;
  try {
    const res = await fetch(url, {
      next: { revalidate: 300 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      return [];
    }
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchCategoryArticles(
  slug: string,
  params?: { page?: number; pageSize?: number }
): Promise<PaginatedResponse<ArticleListItem>> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", params.page.toString());
  if (params?.pageSize) query.set("page_size", params.pageSize.toString());

  const qs = query.toString();
  const url = `${getApiBaseUrl()}/categories/${encodeURIComponent(slug)}/articles${qs ? `?${qs}` : ""}`;

  try {
    const res = await fetch(url, {
      next: { revalidate: 60 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      return { items: [], total: 0, page: 1, page_size: params?.pageSize || 20, total_pages: 0, error: true };
    }
    return await res.json();
  } catch {
    return { items: [], total: 0, page: 1, page_size: params?.pageSize || 20, total_pages: 0, error: true };
  }
}

export interface NewsletterApiResponse {
  success: boolean;
  status: string;
  message: string;
}

export async function subscribeToNewsletter(email: string): Promise<NewsletterApiResponse> {
  const url = `${getApiBaseUrl()}/newsletter/subscribe`;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) {
      return {
        success: false,
        status: "error",
        message: data.detail || "Subscription failed. Please try again.",
      };
    }
    return data;
  } catch {
    return {
      success: false,
      status: "network_error",
      message: "Unable to reach the newsletter server. Please try again later.",
    };
  }
}

export async function verifyNewsletterSubscription(token: string): Promise<NewsletterApiResponse> {
  const url = `${getApiBaseUrl()}/newsletter/verify?token=${encodeURIComponent(token)}`;
  try {
    const res = await fetch(url, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    const data = await res.json();
    return data;
  } catch {
    return {
      success: false,
      status: "network_error",
      message: "Unable to connect to verification service. Please try again.",
    };
  }
}

export async function unsubscribeFromNewsletter(token: string): Promise<NewsletterApiResponse> {
  const url = `${getApiBaseUrl()}/newsletter/unsubscribe?token=${encodeURIComponent(token)}`;
  try {
    const res = await fetch(url, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    const data = await res.json();
    return data;
  } catch {
    return {
      success: false,
      status: "network_error",
      message: "Unable to connect to unsubscription service. Please try again.",
    };
  }
}
