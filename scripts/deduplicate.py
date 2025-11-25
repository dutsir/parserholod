import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.database import init_db, AsyncSessionLocal
from deduplication.deduplicator import Deduplicator


async def main():
    print("=" * 80)
    print("ЗАПУСК ДЕДУПЛИКАЦИИ")
    print("=" * 80)
    
    print("\n[Инициализация] Подключение к базе данных...")
    await init_db()
    print("[Инициализация] База данных готова")
    
    deduplicator = Deduplicator(
        title_threshold=85.0,
        address_threshold=80.0,
        price_diff_percent=15.0,
        area_diff_percent=10.0
    )
    
    async with AsyncSessionLocal() as db:
        print("\n[Дедупликация] Поиск объявлений без продукта...")
        
        stats = await deduplicator.deduplicate_all(db, batch_size=100)
        
        print("\n" + "=" * 80)
        print("РЕЗУЛЬТАТЫ ДЕДУПЛИКАЦИИ")
        print("=" * 80)
        print(f"Обработано объявлений: {stats['processed']}")
        print(f"Создано новых продуктов: {stats['new_products']}")
        print(f"Объединено в существующие продукты: {stats['merged']}")
        print("=" * 80)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())

