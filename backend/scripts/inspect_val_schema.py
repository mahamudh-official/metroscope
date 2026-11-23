import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def verify_db():
    engine = create_async_engine('postgresql+asyncpg://metroscope_user@127.0.0.1:5434/metroscope_val')
    async with engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """))
        tables = [r[0] for r in res.fetchall()]
        print("Tables:", tables)
        
        res = await conn.execute(text("""
            SELECT tablename, indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            ORDER BY tablename, indexname;
        """))
        indexes = res.fetchall()
        print(f"Total indexes: {len(indexes)}")
        for t, idx in indexes:
            print(f"  {t}: {idx}")
            
        res = await conn.execute(text("""
            SELECT
                tc.table_name, kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name 
            FROM 
                information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='public';
        """))
        fks = res.fetchall()
        print(f"Foreign keys: {len(fks)}")
        for fk in fks:
            print(f"  {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify_db())
