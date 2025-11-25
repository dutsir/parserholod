from typing import List, Optional, Tuple
from rapidfuzz import fuzz
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Offer, Product
from database.crud import CRUDProduct, CRUDOffer, CRUDAttribute


class Deduplicator:

    def __init__(
        self,
        title_threshold: float = 85.0,
        address_threshold: float = 80.0,
        price_diff_percent: float = 15.0,
        area_diff_percent: float = 10.0,
    ):
        self.title_threshold = title_threshold
        self.address_threshold = address_threshold
        self.price_diff_percent = price_diff_percent
        self.area_diff_percent = area_diff_percent

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        return " ".join(text.lower().strip().split())

    def _is_price_similar(self, price1: int, price2: int) -> bool:
        if price1 == 0 or price2 == 0:
            return True
        
        max_price = max(price1, price2)
        min_price = min(price1, price2)
        diff_percent = ((max_price - min_price) / min_price) * 100
        
        return diff_percent <= self.price_diff_percent

    def _is_area_similar(self, area1: float, area2: float) -> bool:
        if area1 == 0.0 or area2 == 0.0:
            return True
        
        max_area = max(area1, area2)
        min_area = min(area1, area2)
        diff_percent = ((max_area - min_area) / min_area) * 100
        
        return diff_percent <= self.area_diff_percent

    def calculate_similarity(self, offer1: Offer, offer2: Offer) -> float:
        title1 = self._normalize_text(offer1.title)
        title2 = self._normalize_text(offer2.title)
        address1 = self._normalize_text(offer1.address)
        address2 = self._normalize_text(offer2.address)

        title_similarity = fuzz.token_sort_ratio(title1, title2)
        
        address_similarity = fuzz.token_sort_ratio(address1, address2)
        
        rooms_match = 100.0 if offer1.rooms == offer2.rooms else 0.0
        
        area_match = 100.0 if self._is_area_similar(offer1.area, offer2.area) else 0.0
        
        price_match = 100.0 if self._is_price_similar(offer1.price, offer2.price) else 0.0

        total_similarity = (
            title_similarity * 0.4 +
            address_similarity * 0.3 +
            rooms_match * 0.1 +
            area_match * 0.1 +
            price_match * 0.1
        )

        return total_similarity

    def is_duplicate(self, offer1: Offer, offer2: Offer) -> bool:
        if offer1.website_name == offer2.website_name:
            return False

        similarity = self.calculate_similarity(offer1, offer2)

        return similarity >= self.title_threshold

    async def find_matching_product(
        self, db: AsyncSession, offer: Offer
    ) -> Optional[Product]:
        
        search_queries = []
        
        # 1. Поиск по заголовку (первые 50 символов)
        if offer.title:
            search_queries.append(offer.title[:50])
        
        # 2. Поиск по адресу (если есть)
        if offer.address:
            
            address_words = offer.address.split()[:5]
            if address_words:
                search_queries.append(" ".join(address_words))
        
        # 3. Поиск по ключевым словам из заголовка
        if offer.title:
            
            title_words = offer.title.split()[:4]
            if title_words:
                search_queries.append(" ".join(title_words))
        
        best_match = None
        best_similarity = 0.0
        
        
        for query in search_queries:
            if not query or len(query) < 3:
                continue
                
            products = await CRUDProduct.search(
                db,
                query=query,
                rooms=offer.rooms,
                min_area=offer.area * 0.85 if offer.area > 0 else None,  # Расширили диапазон до ±15%
                max_area=offer.area * 1.15 if offer.area > 0 else None,
                limit=100  
            )

            for product in products:
                if not product.offers:
                    continue

                
                has_same_website = any(
                    existing_offer.website_name == offer.website_name 
                    for existing_offer in product.offers
                )
                if has_same_website:
                    continue

                
                max_product_similarity = 0.0
                for existing_offer in product.offers:
                    similarity = self.calculate_similarity(offer, existing_offer)
                    if similarity > max_product_similarity:
                        max_product_similarity = similarity

                
                if max_product_similarity >= self.title_threshold and max_product_similarity > best_similarity:
                    best_similarity = max_product_similarity
                    best_match = product
                    
                    
                    if best_similarity >= 90.0:
                        return best_match

        return best_match

    async def create_product_from_offer(
        self, db: AsyncSession, offer: Offer
    ) -> Product:
        product = await CRUDProduct.create(
            db,
            title=offer.title,
            address=offer.address,
            district=offer.district,  
            description=offer.description,
            rooms=offer.rooms,
            area=offer.area,
            property_type=offer.property_type,
            image_url=offer.image_url,
            min_price=offer.price
        )

        offer.product_id = product.id
        await db.commit()

        return product

    async def assign_offer_to_product(
        self, db: AsyncSession, offer: Offer, product: Product
    ) -> None:
        
        offer.product_id = product.id
        await db.flush()  
        
        
        await CRUDProduct.update_min_price(db, product.id)
        
        
        await db.commit()

    async def deduplicate_offer(self, db: AsyncSession, offer: Offer) -> Product:
        product = await self.find_matching_product(db, offer)

        if product:
            await self.assign_offer_to_product(db, offer, product)
        else:
            product = await self.create_product_from_offer(db, offer)

        return product

    async def deduplicate_all(self, db: AsyncSession, batch_size: int = 100) -> dict:
        stats = {
            "processed": 0,
            "new_products": 0,
            "merged": 0,
            "errors": 0
        }

        batch_num = 0
        while True:
            offers = await CRUDOffer.get_unassigned(db, limit=batch_size)
            
            if not offers:
                break

            batch_num += 1
            print(f"[Дедупликация] Обработка пачки {batch_num} ({len(offers)} объявлений)...")

            for i, offer in enumerate(offers, 1):
                try:
                    product = await self.find_matching_product(db, offer)
                    
                    if product:
                        await self.assign_offer_to_product(db, offer, product)
                        stats["merged"] += 1
                        
                        
                        if stats["merged"] <= 5:
                            print(f"[Дедупликация] ✓ Объединено: {offer.website_name} -> продукт #{product.id}")
                            print(f"  Заголовок: {offer.title[:60]}...")
                            print(f"  Адрес: {offer.address[:60] if offer.address else '(нет)'}...")
                    else:
                        product = await self.create_product_from_offer(db, offer)
                        stats["new_products"] += 1
                        
                        
                        if stats["new_products"] <= 5:
                            print(f"[Дедупликация] + Новый продукт #{product.id} из {offer.website_name}")
                            print(f"  Заголовок: {offer.title[:60]}...")
                    
                    stats["processed"] += 1
                    
                    if i % 20 == 0:
                        print(f"[Дедупликация] Обработано: {stats['processed']} | Новых: {stats['new_products']} | Объединено: {stats['merged']} | Ошибок: {stats['errors']}")

                except Exception as e:
                    stats["errors"] += 1
                    if stats["errors"] <= 3:
                        import traceback
                        print(f"[Дедупликация] ✗ Ошибка при обработке оффера {i}: {str(e)[:100]}")
                        if stats["errors"] == 1:
                            traceback.print_exc()
                    await db.rollback()
                    continue

        return stats

