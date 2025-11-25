import re
import asyncio
from typing import List, Optional
from urllib.parse import urljoin

from playwright.async_api import Page

from models import Listing
from config import Config
from base_parser import BaseParser
from utils.address_parser import extract_district


class AvitoParser(BaseParser):
    def __init__(self, config: Config):
        super().__init__(config, source_name="avito")

    def get_base_url(self) -> str:
        return "https://www.avito.ru/vladivostok/kvartiry/sdam/na_dlitelnyy_srok-ASgBAgICAkSSA8gQ8AeQUg"

    async def parse_listings_page(self, page: int = 1) -> List[Listing]:
        url = self.get_base_url()
        if page > 1:
            url = f"{url}?p={page}"
        
        page_obj = await self._fetch(url)
        if not page_obj:
            return []
        
        items = []
        try:
            await asyncio.sleep(3)
            
            cards = await page_obj.query_selector_all("div[data-marker='item']")
            if len(cards) == 0:
                cards = await page_obj.query_selector_all("div[class*='iva-item']")
            if len(cards) == 0:
                cards = await page_obj.query_selector_all("article[data-marker='item']")
            
            if len(cards) == 0:
                print(f"[avito] Предупреждение: карточки не найдены на странице {page}")
                return []
            
            for card in cards:
                try:
                    href = None
                    full_url = ""
                    
                    link_selectors = [
                        "a[itemprop='url']",
                        "a[data-marker='item-title']",
                        "a.link-link-MbQDP",
                        "a[href*='/vladivostok/kvartiry/']",
                        "h3 a",
                        "a",
                    ]
                    
                    a = None
                    for selector in link_selectors:
                        a = await card.query_selector(selector)
                        if a:
                            href = await a.get_attribute("href")
                            if href:
                                break
                    
                    if not href:
                        continue
                    
                    full_url = urljoin("https://www.avito.ru", href) if href else ""
                    
                    title = ""
                    title_selectors = [
                        "h3[itemprop='name']",
                        "h3",
                        "a[data-marker='item-title']",
                        "span[itemprop='name']",
                    ]
                    
                    for selector in title_selectors:
                        title_el = await card.query_selector(selector)
                        if title_el:
                            title = await title_el.inner_text()
                            if title:
                                break
                    
                    if not title and a:
                        title = await a.inner_text()
                    
                    title = title.strip() if title else ""
                    
                    price = 0
                    price_selectors = [
                        "meta[itemprop='price']",
                        "span[itemprop='price']",
                        "span[data-marker='item-price']",
                        "span[class*='price-text']",
                    ]
                    
                    for selector in price_selectors:
                        price_el = await card.query_selector(selector)
                        if price_el:
                            if selector.startswith("meta"):
                                price_content = await price_el.get_attribute("content")
                                if price_content:
                                    price = int(re.sub(r"\D", "", price_content) or 0)
                                    break
                            else:
                                price_text = await price_el.inner_text()
                                if price_text:
                                    price = int(re.sub(r"\D", "", price_text) or 0)
                                    if price > 0:
                                        break
                    
                    if price == 0:
                        card_text = await card.inner_text()
                        price_match = re.search(r"(\d+[\s,.]?\d*)\s*₽", card_text)
                        if price_match:
                            price = int(re.sub(r"\D", "", price_match.group(1)) or 0)

                    area = 0.0
                    area_match = re.search(r"(\d+[\.,]?\d*)\s*м²", title.replace(",", "."))
                    if area_match:
                        area = float(area_match.group(1))
                    else:
                        card_text = await card.inner_text()
                        area_match = re.search(r"(\d+[\.,]?\d*)\s*м²", card_text.replace(",", "."))
                        if area_match:
                            area = float(area_match.group(1))
                    
                    rooms = 1
                    rooms_patterns = [
                        r"(\d+)[-\s]*к\.?\s+квартира",
                        r"(\d+)[-\s]*комнат",
                        r"^(\d+)[-\s]*к\.?",
                        r"(\d+)[-\s]*к\.?\s*,",
                    ]
                    
                    for pattern in rooms_patterns:
                        rooms_match = re.search(pattern, title, re.IGNORECASE)
                        if rooms_match:
                            rooms_value = int(rooms_match.group(1))
                            if 1 <= rooms_value <= 10:
                                rooms = rooms_value
                                break
                    
                    if rooms == 1:
                        card_text = await card.inner_text()
                        for pattern in rooms_patterns:
                            rooms_match = re.search(pattern, card_text, re.IGNORECASE)
                            if rooms_match:
                                rooms_value = int(rooms_match.group(1))
                                if 1 <= rooms_value <= 10:
                                    rooms = rooms_value
                                    break
                    
                    property_type = "apartment"
                    external_id = re.sub(r"\D", "", href or full_url)[:32]
                    
                    # Извлекаем адрес
                    address = ""
                    
                    # Основной метод: используем data-marker="item-address" (найден в тестах)
                    address_container = await card.query_selector('div[data-marker="item-address"]')
                    if address_container:
                        try:
                            address_text = await address_container.inner_text()
                            if address_text:
                                # Очищаем от лишних пробелов и переносов строк
                                address = " ".join(address_text.strip().split())
                                # Заменяем множественные пробелы на один
                                address = " ".join(address.split())
                        except Exception:
                            pass
                    
                    # Резервный метод: ищем через itemprop="address"
                    if not address:
                        address_container = await card.query_selector('div[itemprop="address"]')
                        if address_container:
                            try:
                                address_text = await address_container.inner_text()
                                if address_text:
                                    address = " ".join(address_text.strip().split())
                            except Exception:
                                pass
                    
                    # Резервный метод 2: ищем span элементы с адресом (без классов)
                    if not address:
                        try:
                            # Ищем все span в карточке и проверяем на наличие адресных ключевых слов
                            all_spans = await card.query_selector_all("span")
                            address_parts = []
                            
                            for span in all_spans:
                                try:
                                    text = await span.inner_text()
                                    if text and text.strip():
                                        text_lower = text.lower()
                                        # Проверяем на наличие адресных признаков
                                        if any(keyword in text_lower for keyword in ["ул.", "улица", "д.", "дом", "р-н", "район", "пр.", "проспект"]):
                                            address_parts.append(text.strip())
                                except Exception:
                                    continue
                            
                            if address_parts:
                                # Объединяем части адреса, убирая дубликаты
                                seen = set()
                                unique_parts = []
                                for part in address_parts:
                                    if part not in seen:
                                        seen.add(part)
                                        unique_parts.append(part)
                                address = ", ".join(unique_parts)
                        except Exception:
                            pass
                    
                    # Извлекаем район из адреса
                    district = None
                    if address:
                        cleaned_address, extracted_district = extract_district(address)
                        if extracted_district:
                            district = extracted_district
                            address = cleaned_address  # Обновляем адрес без района
                    
                    # Логируем первые несколько адресов для отладки
                    if len(items) < 5:
                        if address:
                            print(f"[avito] ✓ Адрес найден #{len(items)+1}: {address[:100]}")
                            if district:
                                print(f"[avito] ✓ Район извлечен: {district}")
                        else:
                            print(f"[avito] ✗ Адрес не найден для объявления #{len(items)+1}")
                            # Показываем, что мы искали
                            try:
                                test_addr = await card.query_selector('div[data-marker="item-address"]')
                                if test_addr:
                                    test_text = await test_addr.inner_text()
                                    print(f"[avito] Но div[data-marker='item-address'] найден! Текст: {test_text[:100]}")
                                else:
                                    print(f"[avito] div[data-marker='item-address'] не найден в карточке")
                            except Exception as e:
                                print(f"[avito] Ошибка при проверке адреса: {e}")

                    listing = Listing(
                        external_id=external_id or full_url,
                        title=title or full_url,
                        price=price,
                        url=full_url,
                        address=address,  # Адрес без района
                        area=area,
                        rooms=rooms,
                        property_type=property_type,
                        source="avito",
                        district=district,  # Район отдельно
                    )
                    
                    # Проверяем, что адрес действительно в объекте
                    if len(items) < 3:
                        print(f"[avito] Проверка: listing.address = '{listing.address}'")
                    
                    items.append(listing)
                except Exception as e:
                    continue
        finally:
            try:
                if page_obj and not page_obj.is_closed():
                    await page_obj.close()
            except Exception:
                pass
        
        return items

    async def parse_listing_page(self, url: str) -> Optional[Listing]:
        page_obj = await self._fetch(url)
        if not page_obj:
            return None
        
        try:
            title_el = await page_obj.query_selector("h1")
            title = await title_el.inner_text() if title_el else url
            
            price_el = await page_obj.query_selector("meta[itemprop='price']")
            price = 0
            if price_el:
                price_content = await price_el.get_attribute("content")
                if price_content:
                    price = int(re.sub(r"\D", "", price_content) or 0)
            
            external_id = re.sub(r"\D", "", url)[:32]
            
            return Listing(
                external_id=external_id or url,
                title=title,
                price=price,
                url=url,
                address="",
                area=0.0,
                rooms=1,
                property_type="apartment",
                source="avito",
            )
        finally:
            try:
                if page_obj and not page_obj.is_closed():
                    await page_obj.close()
            except Exception:
                pass


