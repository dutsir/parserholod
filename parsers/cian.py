import re
import asyncio
from typing import List, Optional
from urllib.parse import urljoin

from playwright.async_api import Page

from models import Listing
from config import Config
from base_parser import BaseParser
from utils.address_parser import extract_district


class CianParser(BaseParser):

    def __init__(self, config: Config):
        super().__init__(config, source_name="cian")

    def get_base_url(self) -> str:
        return "https://vladivostok.cian.ru/snyat-kvartiru/"

    async def parse_listings_page(self, page: int = 1) -> List[Listing]:
        url = self.get_base_url()
        if page > 1:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}p={page}"

        page_obj = await self._fetch(url)
        if not page_obj:
            return []

        items = []

        try:
            await page_obj.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)
            
            cards = await page_obj.query_selector_all('article[data-name="CardComponent"]')
            if len(cards) == 0:
                cards = await page_obj.query_selector_all('div[data-name="LinkArea"]')
            if len(cards) == 0:
                cards = await page_obj.query_selector_all('div[class*="x31de4314"]')

            for card in cards:
                try:
                    link = await card.query_selector('a[href*="/rent/"]')
                    if not link:
                        continue
                    
                    href = await link.get_attribute("href") or ""
                    if href.startswith("http"):
                        full_url = href
                    else:
                        full_url = urljoin("https://vladivostok.cian.ru", href)

                    external_id_match = re.search(r'/(\d+)/', href)
                    external_id = external_id_match.group(1) if external_id_match else re.sub(r'\D', '', href)[:32]

                    title_el = await card.query_selector('[data-mark="OfferTitle"]')
                    if not title_el:
                        title_el = link
                    title_full_text = await title_el.inner_text() if title_el else ""
                    title_full_text = title_full_text.strip()
                    
                    title = title_full_text.split(',')[0].strip() if ',' in title_full_text else title_full_text
                    price_el = await card.query_selector('[data-mark="MainPrice"]')
                    price = 0
                    if price_el:
                        price_text = await price_el.inner_text()
                        price = int(re.sub(r'\D', '', price_text) or 0)

                    address_parts = []
                    geo_labels = await card.query_selector_all('[data-name="GeoLabel"]')
                    if not geo_labels:
                        geo_labels = await card.query_selector_all('[data-mark="GeoLabel"]')
                    if not geo_labels:
                        geo_el = await card.query_selector('[data-mark="Geo"]')
                        if geo_el:
                            geo_labels = [geo_el]
                    
                    for geo_el in geo_labels:
                        geo_text = await geo_el.inner_text()
                        if geo_text:
                            address_parts.append(geo_text.strip())
                    
                    address = ", ".join(address_parts) if address_parts else ""
                    
                    district = None
                    if address:
                        cleaned_address, extracted_district = extract_district(address)
                        if extracted_district:
                            district = extracted_district
                            address = cleaned_address

                    area = 0.0
                    
                    def find_area_in_text(text: str) -> float:
                        if not text:
                            return 0.0
                        
                        if ',' in text:
                            parts = text.split(',', 2)
                            if len(parts) > 1:
                                area_text = parts[1].strip()
                                area_patterns = [
                                    r'(\d+)[\.,]\d+\s*м²',
                                    r'(\d+)\s*м²',
                                    r'(\d+)[\.,]\d+\s*м2',
                                    r'(\d+)\s*м2',
                                ]
                                
                                for pattern in area_patterns:
                                    area_match = re.search(pattern, area_text)
                                    if area_match:
                                        return float(area_match.group(1))
                        
                        area_patterns = [
                            r'(\d+)[\.,]\d+\s*м²',
                            r'(\d+)\s*м²',
                            r'(\d+)[\.,]\d+\s*м2',
                            r'(\d+)\s*м2',
                            r'(\d+)\s*м\s',
                        ]
                        
                        for pattern in area_patterns:
                            area_match = re.search(pattern, text)
                            if area_match:
                                return float(area_match.group(1))
                        
                        return 0.0
                    
                    area = find_area_in_text(title_full_text)
                    
                    if area == 0.0:
                        subtitle_el = await card.query_selector('[data-mark="OfferSubtitle"]')
                        if subtitle_el:
                            subtitle_text = await subtitle_el.inner_text()
                            if subtitle_text:
                                area = find_area_in_text(subtitle_text.strip())
                    
                    if area == 0.0:
                        desc_el = await card.query_selector('[data-name="Description"]')
                        if desc_el:
                            desc_text = await desc_el.inner_text()
                            if desc_text:
                                area = find_area_in_text(desc_text)

                    rooms = 1
                    rooms_patterns = [
                        r'(\d+)[-\s]*комн\.?',
                        r'(\d+)[-\s]*к\.?\s+квартира',
                        r'^(\d+)[-\s]*к\.?',
                        r'(\d+)[-\s]*к\.?\s*,',
                    ]
                    
                    for pattern in rooms_patterns:
                        rooms_match = re.search(pattern, title_full_text, re.IGNORECASE)
                        if rooms_match:
                            rooms_value = int(rooms_match.group(1))
                            if 1 <= rooms_value <= 10:
                                rooms = rooms_value
                                break
                    
                    if 'студия' in title_full_text.lower() or 'studio' in title_full_text.lower():
                        rooms = 1
                        property_type = "studio"
                    else:
                        property_type = "apartment"
                    
                    floor = None
                    total_floors = None
                    floor_match = re.search(r'(\d+)/(\d+)\s*этаж', title_full_text)
                    if floor_match:
                        floor = int(floor_match.group(1))
                        total_floors = int(floor_match.group(2))

                    desc_el = await card.query_selector('[data-mark="Description"]')
                    description = await desc_el.inner_text() if desc_el else None
                    if description:
                        description = description.strip()

                    img_el = await card.query_selector('img[src*="cdn-p.cian.site"]')
                    image_url = await img_el.get_attribute('src') if img_el else None

                    listing = Listing(
                        external_id=external_id or full_url,
                        title=title or full_url,
                        price=price,
                        url=full_url,
                        address=address,
                        area=area,
                        rooms=rooms,
                        property_type=property_type,
                        source="cian",
                        description=description,
                        images=[image_url] if image_url else None,
                        district=district,
                        floor=floor,
                        total_floors=total_floors
                    )
                    
                    items.append(listing)

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
            title_el = await page_obj.query_selector('h1')
            title_full_text = await title_el.inner_text() if title_el else url
            title_full_text = title_full_text.strip()
            
            title = title_full_text.split(',')[0].strip() if ',' in title_full_text else title_full_text
            price = 0
            price_selectors = [
                '[itemprop="price"]',
                '[data-mark="MainPrice"]',
                'meta[itemprop="price"]',
            ]
            
            for selector in price_selectors:
                price_el = await page_obj.query_selector(selector)
                if price_el:
                    if selector.startswith('meta'):
                        price_content = await price_el.get_attribute("content")
                        if price_content:
                            price = int(re.sub(r'\D', '', price_content) or 0)
                            break
                    else:
                        price_text = await price_el.inner_text()
                        if price_text:
                            price = int(re.sub(r'\D', '', price_text) or 0)
                            if price > 0:
                                break

            address = ""
            address_selectors = [
                '[data-name="Geo"]',
                '[data-mark="GeoLabel"]',
                '[itemprop="address"]',
                '.address',
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
            area_patterns = [
                r'(\d+)[\.,]\d+\s*м²',
                r'(\d+)\s*м²',
                r'(\d+)[\.,]\d+\s*м2',
                r'(\d+)\s*м2',
                r'(\d+)\s*м\s',
            ]
            
            for pattern in area_patterns:
                area_match = re.search(pattern, title_full_text)
                if area_match:
                    area = float(area_match.group(1))
                    break
            
            if area == 0.0:
                area_el = await page_obj.query_selector('[data-name="Area"]')
                if area_el:
                    area_text = await area_el.inner_text()
                    if area_text:
                        area_match = re.search(r'(\d+)[\.,]', area_text)
                        if area_match:
                            area = float(area_match.group(1))
                        else:
                            area_match = re.search(r'(\d+)', area_text)
                            if area_match:
                                area = float(area_match.group(1))

            rooms = 1
            rooms_patterns = [
                r'(\d+)[-\s]*комн\.?',
                r'(\d+)[-\s]*к\.?\s+квартира',
                r'^(\d+)[-\s]*к\.?',
            ]
            
            for pattern in rooms_patterns:
                rooms_match = re.search(pattern, title_full_text, re.IGNORECASE)
                if rooms_match:
                    rooms_value = int(rooms_match.group(1))
                    if 1 <= rooms_value <= 10:
                        rooms = rooms_value
                        break
            
            if 'студия' in title_full_text.lower() or 'studio' in title_full_text.lower():
                rooms = 1
                property_type = "studio"
            else:
                property_type = "apartment"
            
            floor = None
            total_floors = None
            floor_match = re.search(r'(\d+)/(\d+)\s*этаж', title_full_text)
            if floor_match:
                floor = int(floor_match.group(1))
                total_floors = int(floor_match.group(2))

            external_id = re.sub(r'\D', '', url)[:32]

            desc_el = await page_obj.query_selector('[data-name="Description"]')
            description = await desc_el.inner_text() if desc_el else None
            if description:
                description = description.strip()

            return Listing(
                external_id=external_id or url,
                title=title,
                price=price,
                url=url,
                address=address,
                area=area,
                rooms=rooms,
                property_type=property_type,
                source="cian",
                description=description,
                district=district,
                floor=floor,
                total_floors=total_floors
            )

        except Exception:
            return None
        finally:
            try:
                if page_obj and not page_obj.is_closed():
                    await page_obj.close()
            except Exception:
                pass

