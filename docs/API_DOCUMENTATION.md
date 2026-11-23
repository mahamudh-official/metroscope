# MetroScope API v1 Documentation

**Base URL:** `/api/v1`  
**API Specification:** OpenAPI 3.1.0 / FastAPI  
**Data Exchange Format:** JSON (`application/json`)  
**Standard Character Encoding:** UTF-8  

---

## 1. Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Operational health status and PostgreSQL connectivity |
| `GET` | `/api/v1/articles` | Paginated news discovery articles with category and search filtering |
| `GET` | `/api/v1/articles/{slug}` | Detailed discovery metadata and publisher attribution by slug |
| `GET` | `/api/v1/categories` | Editorial categories with active article count |
| `GET` | `/api/v1/categories/{slug}/articles` | Paginated articles within a specific category |

---

## 2. Endpoint Details

### 2.1. `GET /api/v1/health`
Checks backend service availability and database pool readiness.

**Response `200 OK`:**
```json
{
  "status": "ok",
  "environment": "production",
  "database_connected": true,
  "version": "0.1.0"
}
```

---

### 2.2. `GET /api/v1/articles`
Returns paginated list of news articles. Supports category and search keyword filtering.

**Query Parameters:**
- `page` (optional integer, default `1`, min `1`): Page number.
- `page_size` (optional integer, default `20`, min `1`, max `100`): Records per page.
- `category` (optional string): Filter by category slug (e.g. `technology`, `us`, `business`).
- `q` (optional string): Case-insensitive keyword search against article title and summary.

**Response `200 OK`:**
```json
{
  "items": [
    {
      "id": 142,
      "title": "Federal Reserve Holds Benchmark Interest Rate Steady Amid Labor Market Resilience",
      "slug": "federal-reserve-holds-benchmark-interest-rate-steady-amid-labor-market-resilience-b4e1",
      "description": "Monetary policy committee maintains federal funds rate corridor, citing moderate inflation progress.",
      "canonical_url": "https://www.bloomberg.com/news/articles/2026-11-07/fed-holds-benchmark-interest-rate",
      "image_url": null,
      "language": "en",
      "country": "US",
      "published_at": "2026-11-07T14:30:00Z",
      "discovered_at": "2026-11-07T14:45:12Z",
      "source": {
        "id": 18,
        "name": "Bloomberg",
        "domain": "bloomberg.com",
        "website_url": "https://bloomberg.com",
        "country": "US",
        "language": "en"
      },
      "category": {
        "id": 4,
        "name": "Business",
        "slug": "business",
        "description": "Corporate updates, macroeconomics, finance, and trade",
        "is_active": true
      }
    }
  ],
  "total": 1420,
  "page": 1,
  "page_size": 20,
  "total_pages": 71
}
```

---

### 2.3. `GET /api/v1/articles/{slug}`
Retrieves complete discovery metadata and publisher attribution record for an article.

**Path Parameter:**
- `slug` (string, required): Unique article URL slug.

**Response `200 OK`:**
```json
{
  "id": 142,
  "title": "Federal Reserve Holds Benchmark Interest Rate Steady Amid Labor Market Resilience",
  "slug": "federal-reserve-holds-benchmark-interest-rate-steady-amid-labor-market-resilience-b4e1",
  "description": "Monetary policy committee maintains federal funds rate corridor, citing moderate inflation progress.",
  "original_url": "https://www.bloomberg.com/news/articles/2026-11-07/fed-holds-benchmark-interest-rate?utm_source=twitter",
  "canonical_url": "https://www.bloomberg.com/news/articles/2026-11-07/fed-holds-benchmark-interest-rate",
  "canonical_url_hash": "a8f3b216c59d4e92781bcf70415a7703816a73c1d93b95feef914a3875a64019",
  "image_url": null,
  "language": "en",
  "country": "US",
  "published_at": "2026-11-07T14:30:00Z",
  "discovered_at": "2026-11-07T14:45:12Z",
  "status": "published",
  "created_at": "2026-11-07T14:45:12Z",
  "updated_at": "2026-11-07T14:45:12Z",
  "source": {
    "id": 18,
    "name": "Bloomberg",
    "domain": "bloomberg.com",
    "website_url": "https://bloomberg.com",
    "country": "US",
    "language": "en"
  },
  "category": {
    "id": 4,
    "name": "Business",
    "slug": "business",
    "description": "Corporate updates, macroeconomics, finance, and trade",
    "is_active": true
  }
}
```

**Response `404 Not Found`:**
```json
{
  "detail": "Article not found"
}
```

---

### 2.4. `GET /api/v1/categories`
Returns all active editorial categories with current article counts.

**Response `200 OK`:**
```json
[
  {
    "id": 1,
    "name": "World",
    "slug": "world",
    "description": "Global events, international relations, and diplomatic affairs",
    "is_active": true,
    "article_count": 215,
    "created_at": "2026-11-07T00:00:00Z",
    "updated_at": "2026-11-07T00:00:00Z"
  },
  {
    "id": 2,
    "name": "US",
    "slug": "us",
    "description": "Domestic American reporting, state policies, and national affairs",
    "is_active": true,
    "article_count": 340,
    "created_at": "2026-11-07T00:00:00Z",
    "updated_at": "2026-11-07T00:00:00Z"
  }
]
```

---

### 2.5. `GET /api/v1/categories/{slug}/articles`
Returns paginated articles assigned to the specified category slug.

**Path Parameter:**
- `slug` (string, required): Category slug (e.g. `technology`).

**Query Parameters:**
- `page` (optional integer, default `1`)
- `page_size` (optional integer, default `20`)

**Response `200 OK`:**
```json
{
  "items": [ ... ],
  "total": 128,
  "page": 1,
  "page_size": 20,
  "total_pages": 7
}
```

**Response `404 Not Found`:**
```json
{
  "detail": "Category 'invalid-slug' not found"
}
```
