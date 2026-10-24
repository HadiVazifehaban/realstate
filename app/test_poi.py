import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT cell_lat, cell_lng, payload, fetched_at FROM poi_cache WHERE cell_lat = 35.672000000000004 AND cell_lng = 51.368"))
        rows = result.all()
        print("Direct query rows:", len(rows))
        for row in rows:
            print("payload keys:", list((row._mapping['payload'] or {}).keys()))
            print("payload transport:", (row._mapping['payload'] or {}).get('transport'))
        
        from app.services.poi_service import _cached_cells_within
        rows2 = await _cached_cells_within(session, 35.672, 51.368, 500)
        print("_cached_cells_within rows:", len(rows2))
        for row in rows2:
            print("cell_lat:", row['cell_lat'], "fetched_at:", row['fetched_at'], "buckets:", list((row['payload'] or {}).keys()))

asyncio.run(main())
