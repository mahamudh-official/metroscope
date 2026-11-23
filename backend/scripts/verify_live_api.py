import asyncio
import httpx
from app.main import create_app

async def test_api():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://localhost:8000') as client:
        # 1. Health check
        r_health = await client.get('/api/v1/health')
        print('GET /api/v1/health status:', r_health.status_code)
        print('Health body:', r_health.json())
        assert r_health.status_code == 200
        assert r_health.json().get('database_connected') is True

        # 2. Articles list
        r_articles = await client.get('/api/v1/articles?page=1&limit=5')
        print('\nGET /api/v1/articles status:', r_articles.status_code)
        articles_data = r_articles.json()
        print('Total articles in DB:', articles_data.get('total'))
        items = articles_data.get('items', [])
        print(f'Retrieved {len(items)} items on page 1')
        assert r_articles.status_code == 200
        assert len(items) > 0
        
        first_slug = items[0]['slug']
        print('Sample article title:', items[0]['title'])
        print('Sample article slug:', first_slug)
        print('Sample article source:', items[0].get('source'))
        print('Sample article category:', items[0].get('category'))

        # 3. Single article by slug
        r_single = await client.get(f'/api/v1/articles/{first_slug}')
        print(f'\nGET /api/v1/articles/{first_slug} status:', r_single.status_code)
        single_data = r_single.json()
        print('Single article title:', single_data.get('title'))
        print('Original URL:', single_data.get('original_url'))
        print('Canonical URL:', single_data.get('canonical_url'))
        assert r_single.status_code == 200
        assert single_data.get('slug') == first_slug

        # 4. Categories list
        r_cats = await client.get('/api/v1/categories')
        print('\nGET /api/v1/categories status:', r_cats.status_code)
        cats = r_cats.json()
        print(f'Total categories: {len(cats)}')
        assert r_cats.status_code == 200
        assert len(cats) >= 10
        for c in cats[:3]:
            print(f"  Category: {c.get('name')} (slug={c.get('slug')})")

        # 5. Articles by category
        r_cat_articles = await client.get('/api/v1/categories/us/articles?limit=5')
        print('\nGET /api/v1/categories/us/articles status:', r_cat_articles.status_code)
        cat_articles = r_cat_articles.json()
        print(f"Category 'us' articles count: {cat_articles.get('total')}")
        assert r_cat_articles.status_code == 200

    print('\nALL LIVE API ENDPOINT VERIFICATIONS PASSED!')

if __name__ == '__main__':
    asyncio.run(test_api())
