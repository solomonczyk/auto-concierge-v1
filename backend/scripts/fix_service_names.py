import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.db.session import async_session_local
from app.models.models import Service
from sqlalchemy import select

async def fix_service_names():
    try:
        async with async_session_local() as db:
            print("Fetching services to fix names...")
            result = await db.execute(select(Service))
            services = result.scalars().all()
            
            fixed_count = 0
            for service in services:
                # Basic fix: capitalize first letter if it's lowercase
                if service.name and service.name[0].islower():
                    old_name = service.name
                    # Capitalize first letter, keep rest as is
                    service.name = service.name[0].upper() + service.name[1:]
                    print(f"Fixed: '{old_name}' -> '{service.name}'")
                    fixed_count += 1
            
            if fixed_count > 0:
                await db.commit()
                print(f"Successfully fixed {fixed_count} service names.")
            else:
                print("No services needed fixing.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(fix_service_names())
