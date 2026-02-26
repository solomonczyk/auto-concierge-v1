
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.db.session import async_session_local
from app.models.models import Service
from sqlalchemy import select, update

REPAIR_MAP = {
    "амена масла": "Замена масла и фильтра",
    "иагностика подвески": "Диагностика ходовой",
    "амена тормозных колодок": "Замена тормозных колодок",
    "омпьютерная диагностика": "Компьютерная диагностика",
    "амена": "Замена масла",
    "аправка кондиционера": "Заправка кондиционера",
    "ойка двигателя": "Мойка двигателя",
    "амена свечей зажигания": "Замена свечей зажигания"
}

async def repair():
    async with async_session_local() as db:
        print("Starting DB repair...")
        result = await db.execute(select(Service))
        services = result.scalars().all()
        
        for s in services:
            if s.name in REPAIR_MAP:
                new_name = REPAIR_MAP[s.name]
                print(f"Repairing: '{s.name}' -> '{new_name}'")
                s.name = new_name
            elif not s.name[0].isupper():
                # Generic fix for others
                fixed = s.name.capitalize()
                print(f"Generic fix: '{s.name}' -> '{fixed}'")
                s.name = fixed
        
        await db.commit()
        print("Repair complete!")

if __name__ == "__main__":
    asyncio.run(repair())
