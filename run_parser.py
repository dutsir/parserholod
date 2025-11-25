import sys
import warnings
import os

os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")
warnings.simplefilter("ignore", ResourceWarning)
warnings.simplefilter("ignore", RuntimeWarning)

if sys.platform == "win32":
    import logging
    import asyncio
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    logging.getLogger("playwright").setLevel(logging.ERROR)
    # Для Playwright нужен ProactorEventLoop на Windows
    if sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import asyncio
from datetime import datetime

from config import Config
from models import Listing
from database.database import init_db, AsyncSessionLocal
from database.crud import CRUDOffer, CRUDProduct
from deduplication.deduplicator import Deduplicator

from parsers.avito import AvitoParser
from parsers.farpost import FarPostParser
from parsers.cian import CianParser


async def run_parser(parser_cls, config: Config, max_pages: int) -> list[Listing]:
    parser_name = parser_cls.__name__.replace("Parser", "")
    print(f"\n[{parser_name}] Запуск парсера...")
    try:
        async with parser_cls(config) as parser:
            listings = await parser.parse_all(max_pages=max_pages)
            print(f"[{parser_name}] Завершено: найдено {len(listings)} объявлений")
            return listings
    except Exception as e:
        import traceback
        print(f"[{parser_name}] ОШИБКА: {str(e)}")
        print(f"[{parser_name}] Детали ошибки:")
        traceback.print_exc()
        return []


def deduplicate_listings(listings: list[Listing], use_address: bool = False) -> list[Listing]:
    """
    Удаляет дубликаты из списка объявлений перед сохранением.
    
    Args:
        listings: Список объявлений для дедупликации
        use_address: Если True, использует адрес для определения дубликатов (медленнее)
    
    Returns:
        Список уникальных объявлений
    """
    if not listings:
        return []
    
    unique_listings = []
    seen_urls = set()
    seen_addresses = set() if use_address else None
    
    duplicates_by_url = 0
    duplicates_by_address = 0
    
    for listing in listings:
        # Метод 1: Проверка по URL (быстро)
        if listing.url in seen_urls:
            duplicates_by_url += 1
            continue
        seen_urls.add(listing.url)
        
        # Метод 2: Проверка по адресу + цена + площадь (если включено)
        if use_address and listing.address:
            # Нормализуем адрес для сравнения
            normalized_address = " ".join(listing.address.lower().strip().split())
            address_key = f"{normalized_address}_{listing.price}_{listing.area}_{listing.rooms}"
            
            if address_key in seen_addresses:
                duplicates_by_address += 1
                continue
            seen_addresses.add(address_key)
        
        unique_listings.append(listing)
    
    if duplicates_by_url > 0 or duplicates_by_address > 0:
        print(f"[Дедупликация] Удалено дубликатов: по URL={duplicates_by_url}, по адресу={duplicates_by_address}")
        print(f"[Дедупликация] Уникальных объявлений: {len(unique_listings)} из {len(listings)}")
    
    return unique_listings


async def save_to_database(listings: list[Listing], deduplicate: bool = True, use_address_dedup: bool = False) -> None:
    print(f"\n[БД] Сохранение {len(listings)} объявлений в базу данных...")
    
    # Дедупликация перед сохранением
    if deduplicate:
        print(f"[Дедупликация] Удаление дубликатов перед сохранением...")
        listings = deduplicate_listings(listings, use_address=use_address_dedup)
        print(f"[Дедупликация] После дедупликации: {len(listings)} объявлений")
    
    async with AsyncSessionLocal() as db:
        saved_count = 0
        skipped_count = 0
        error_count = 0
        
        for i, listing in enumerate(listings, 1):
            try:
                # Проверяем, есть ли уже такое объявление в БД по URL
                existing = await CRUDOffer.get_by_url(db, listing.url)
                if existing:
                    skipped_count += 1
                    if i % 50 == 0:
                        print(f"[БД] Обработано: {i}/{len(listings)} | Сохранено: {saved_count} | Пропущено: {skipped_count} | Ошибок: {error_count}")
                    continue
                
                # Сохраняем объявление БЕЗ product_id (дедупликация создаст продукты и свяжет их)
                offer = await CRUDOffer.create(db, listing, product_id=None)
                saved_count += 1
                
                # Логируем первые несколько адресов для проверки
                if saved_count <= 5:
                    print(f"[БД] Сохранено объявление #{saved_count}:")
                    print(f"  URL: {listing.url[:60]}...")
                    print(f"  Адрес в listing: '{listing.address[:80] if listing.address else '(пусто)'}'")
                    print(f"  Адрес в offer: '{offer.address[:80] if offer.address else '(пусто)'}'")
                    print(f"  Цена: {listing.price}, Комнат: {listing.rooms}, Площадь: {listing.area}")
                
                if i % 50 == 0:
                    print(f"[БД] Обработано: {i}/{len(listings)} | Сохранено: {saved_count} | Пропущено: {skipped_count} | Ошибок: {error_count}")
                
            except Exception as e:
                error_count += 1
                if error_count <= 3:  # Показываем первые 3 ошибки
                    import traceback
                    print(f"[БД] Ошибка при сохранении объявления {i}: {str(e)[:100]}")
                    if error_count == 1:
                        traceback.print_exc()
                await db.rollback()
                continue
        
        print(f"[БД] Готово: Сохранено {saved_count}, Пропущено {skipped_count}, Ошибок {error_count}")


async def run_deduplication() -> None:
    print(f"\n[Дедупликация] Запуск дедупликации...")
    deduplicator = Deduplicator(
        title_threshold=85.0,
        address_threshold=80.0,
        price_diff_percent=15.0,
        area_diff_percent=10.0
    )
    
    async with AsyncSessionLocal() as db:
        stats = await deduplicator.deduplicate_all(db, batch_size=100)
        print(f"[Дедупликация] Завершено: Обработано {stats['processed']}, Новых продуктов {stats['new_products']}, Объединено {stats['merged']}")


async def main():
    print("=" * 80)
    print("СТАРТ ПАРСИНГА")
    print("=" * 80)
    
    print("\n[Инициализация] Подключение к базе данных...")
    await init_db()
    print("[Инициализация] База данных готова")
    
    config = Config.from_env()
    max_pages = 10
    
    print(f"\n[Парсинг] Запуск парсеров ({max_pages} страниц с каждого сайта)...")
    print("-" * 80)
    
    tasks = [
        run_parser(AvitoParser, config, max_pages),
        run_parser(FarPostParser, config, max_pages),
        run_parser(CianParser, config, max_pages),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_listings = []
    parser_names = ["Avito", "FarPost", "CIAN"]
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            import traceback
            print(f"\n[ОШИБКА] {parser_names[i]}: {result}")
            print(f"[ОШИБКА] {parser_names[i]} Детали:")
            traceback.print_exception(type(result), result, result.__traceback__)
        elif isinstance(result, list):
            all_listings.extend(result)
        else:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] {parser_names[i]}: Неожиданный тип результата: {type(result)}")
    
    print("-" * 80)
    print(f"\n[Итого] Всего собрано объявлений: {len(all_listings)}")
    
    if all_listings:
        # Дедупликация перед сохранением
        # use_address_dedup=True - использовать адрес для дедупликации (медленнее, но надежнее)
        # use_address_dedup=False - использовать только URL (быстрее)
        await save_to_database(all_listings, deduplicate=True, use_address_dedup=False)
    
    await run_deduplication()
    
    print("\n" + "=" * 80)
    print("ПАРСИНГ ЗАВЕРШЕН")
    print("=" * 80)


def _suppress_del_exceptions():
    import asyncio.proactor_events
    import asyncio.base_subprocess
    
    original_del_proactor = asyncio.proactor_events._ProactorBasePipeTransport.__del__
    original_del_subprocess = asyncio.base_subprocess.BaseSubprocessTransport.__del__
    
    def safe_del_proactor(self):
        try:
            original_del_proactor(self)
        except (ValueError, RuntimeError, AttributeError):
            pass
    
    def safe_del_subprocess(self):
        try:
            original_del_subprocess(self)
        except (ValueError, RuntimeError, AttributeError):
            pass
    
    asyncio.proactor_events._ProactorBasePipeTransport.__del__ = safe_del_proactor
    asyncio.base_subprocess.BaseSubprocessTransport.__del__ = safe_del_subprocess

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            _suppress_del_exceptions()
        except Exception:
            pass
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        import gc
        gc.collect()
        if sys.platform == "win32":
            import time
            time.sleep(0.5)

