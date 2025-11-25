import re
import asyncio
from typing import List, Optional
from urllib.parse import urljoin

from playwright.async_api import Page

from models import Listing
from config import Config
from base_parser import BaseParser
from utils.address_parser import extract_district


class FarPostParser(BaseParser):
    def __init__(self, config: Config):
        super().__init__(config, source_name="farpost")

    def get_base_url(self) -> str:
        return "https://www.farpost.ru/vladivostok/realty/rent_flats/#center=131.95720572019204%2C43.13726843144687&zoom=10.834896068990224"

    async def parse_listings_page(self, page: int = 1) -> List[Listing]:
        url = self.get_base_url()
        if page > 1:
            if "?" in url:
                url = f"{url}&page={page}"
            elif "#" in url:
                base_url, anchor = url.split("#", 1)
                url = f"{base_url}?page={page}#{anchor}"
            else:
                url = f"{url}?page={page}"
        
        page_obj = await self._fetch(url)
        if not page_obj:
            return []
        
        items = []
        try:
            await page_obj.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            
            rows = await page_obj.query_selector_all(".bull-item__cell")
            if len(rows) == 0:
                rows = await page_obj.query_selector_all("div[class*='bull-item__cell']")
            if len(rows) == 0:
                rows = await page_obj.query_selector_all(".descriptionCell")
            
            for row in rows:
                try:
                    a = await row.query_selector("a.bull-item__self-link")
                    if not a:
                        a = await row.query_selector("a")
                    if not a:
                        continue
                    
                    href = await a.get_attribute("href")
                    full_url = urljoin("https://www.farpost.ru", href) if href else ""
                    
                    title = await a.inner_text()
                    title = title.strip()
                    
                    price = 0
                    price_selectors = [
                        'div.price-block__price[data-role="price"]',
                        'div[data-price]',
                        'div.price-block__final-price',
                        'div.finalPrice',
                        'span[data-bulletin-price]',
                        'span[itemprop="price"]',
                    ]
                    
                    for selector in price_selectors:
                        price_el = await row.query_selector(selector)
                        if price_el:
                            price_attr = await price_el.get_attribute("data-price")
                            if price_attr:
                                price = int(re.sub(r"\D", "", price_attr) or 0)
                                if price > 0:
                                    break
                            
                            price_attr = await price_el.get_attribute("data-bulletin-price")
                            if price_attr:
                                try:
                                    price = int(price_attr)
                                    if price > 0:
                                        break
                                except ValueError:
                                    pass
                            
                            price_text = await price_el.inner_text()
                            if price_text:
                                price = int(re.sub(r"\D", "", price_text) or 0)
                                if price > 0:
                                    break
                    
                    address = ""
                    address_selectors = [
                        '.bull-item__annotation',
                        '.bull-item__address',
                        '.bull-item__geo',
                        '[itemprop="address"]',
                    ]
                    
                    for selector in address_selectors:
                        address_el = await row.query_selector(selector)
                        if address_el:
                            address_text = await address_el.inner_text()
                            if address_text:
                                address = address_text.strip()
                                break
                    
                    if not address and a:
                        link_text = await a.inner_text()
                        if link_text and ',' in link_text:
                            parts = link_text.split(',', 1)
                            if len(parts) > 1:
                                address = parts[1].strip()
                    
                    district = None
                    if address:
                        cleaned_address, extracted_district = extract_district(address)
                        if extracted_district:
                            district = extracted_district
                            address = cleaned_address
                    
                    area = 0.0
                    area_selectors = [
                        '.bull-item__annotation',
                        '.bull-item__area',
                        '.bull-item__params',
                    ]
                    
                    area_patterns = [
                        r"(\d+[\.,]?\d*)\s*кв\.?\s*м\.?",
                        r"(\d+[\.,]?\d*)\s*м²",
                        r"(\d+[\.,]?\d*)\s*м2",
                    ]
                    
                    for selector in area_selectors:
                        area_el = await row.query_selector(selector)
                        if area_el:
                            area_text = await area_el.inner_text()
                            if area_text:
                                for pattern in area_patterns:
                                    area_match = re.search(pattern, area_text, re.IGNORECASE)
                                    if area_match:
                                        area = float(area_match.group(1).replace(',', '.'))
                                        break
                                if area > 0:
                                    break
                    
                    if area == 0.0:
                        card_text = await row.inner_text()
                        for pattern in area_patterns:
                            area_match = re.search(pattern, card_text, re.IGNORECASE)
                            if area_match:
                                area = float(area_match.group(1).replace(',', '.'))
                                break
                    
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
                        card_text = await row.inner_text()
                        for pattern in rooms_patterns:
                            rooms_match = re.search(pattern, card_text, re.IGNORECASE)
                            if rooms_match:
                                rooms_value = int(rooms_match.group(1))
                                if 1 <= rooms_value <= 10:
                                    rooms = rooms_value
                                    break
                    
                    property_type = "apartment"
                    if "студия" in title.lower() or "studio" in title.lower():
                        property_type = "studio"
                    
                    external_id = re.sub(r"\D", "", href or full_url)[:32]
                    
                    items.append(
                        Listing(
                            external_id=external_id or full_url,
                            title=title or full_url,
                            price=price,
                            url=full_url,
                            address=address,
                            area=area,
                            rooms=rooms,
                            property_type=property_type,
                            source="farpost",
                            district=district,
                        )
                    )
                except Exception:
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
            
            price = 0
            price_selectors = [
                'span[data-bulletin-price]',
                'span[itemprop="price"]',
                'span.viewbull-summary-price__value',
            ]
            
            for selector in price_selectors:
                price_el = await page_obj.query_selector(selector)
                if price_el:
                    price_attr = await price_el.get_attribute("data-bulletin-price")
                    if price_attr:
                        try:
                            price = int(price_attr)
                            break
                        except ValueError:
                            pass
                    
                    price_text = await price_el.inner_text()
                    if price_text:
                        price = int(re.sub(r"\D", "", price_text) or 0)
                        if price > 0:
                            break
            
            address = ""
            address_selectors = [
                '[itemprop="address"]',
                '.viewbull-summary-address',
                '.bull-item__address',
            ]
            
            for selector in address_selectors:
                address_el = await page_obj.query_selector(selector)
                if address_el:
                    address_text = await address_el.inner_text()
                    if address_text:
                        address = address_text.strip()
                        break
            
            district = None
            if address:
                cleaned_address, extracted_district = extract_district(address)
                if extracted_district:
                    district = extracted_district
                    address = cleaned_address
            
            area = 0.0
            area_el = await page_obj.query_selector('[data-name="Area"]')
            if not area_el:
                area_el = await page_obj.query_selector('.bull-item__area')
            if area_el:
                area_text = await area_el.inner_text()
                if area_text:
                    area_match = re.search(r'(\d+[\.,]?\d*)', area_text)
                    if area_match:
                        area = float(area_match.group(1).replace(',', '.'))
            
            rooms = 1
            rooms_match = re.search(r'(\d+)[-\s]*комн', title.lower())
            if rooms_match:
                rooms = int(rooms_match.group(1))
            elif 'студия' in title.lower():
                rooms = 1
            
            property_type = "apartment"
            if 'студия' in title.lower():
                property_type = "studio"
            
            external_id = re.sub(r"\D", "", url)[:32]
            
            return Listing(
                external_id=external_id or url,
                title=title,
                price=price,
                url=url,
                address=address,
                area=area,
                rooms=rooms,
                property_type=property_type,
                source="farpost",
                district=district,
            )
        finally:
            try:
                if page_obj and not page_obj.is_closed():
                    await page_obj.close()
            except Exception:
                pass


