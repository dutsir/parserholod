import asyncio
import random
import sys
import warnings
import os
from abc import ABC, abstractmethod
from typing import List, Optional

os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")
warnings.simplefilter("ignore", ResourceWarning)
warnings.simplefilter("ignore", RuntimeWarning)

if sys.platform == "win32":
    import logging
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    logging.getLogger("playwright").setLevel(logging.ERROR)

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from models import Listing
from config import Config
from utils.proxy_manager import ProxyManager
from utils.user_agent_manager import UserAgentManager
from utils.validator import Validator
from utils.captcha_solver import CaptchaSolver


class BaseParser(ABC):

    def __init__(self, config: Config, source_name: str):
        self.config = config
        self.source_name = source_name
        self.proxy_manager = ProxyManager(config.proxies, config.proxy_rotation)
        self.user_agent_manager = UserAgentManager(config.user_agents, config.user_agent_rotation)
        self.validator = Validator(config)
        self.captcha_solver = CaptchaSolver(config)
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def __aenter__(self):
        try:
            print(f"[{self.source_name}] Инициализация Playwright...")
            self.playwright = await async_playwright().start()
            print(f"[{self.source_name}] Запуск браузера...")
            self.browser = await self._create_browser()
            print(f"[{self.source_name}] Браузер готов")
            return self
        except Exception as e:
            print(f"[{self.source_name}] Ошибка инициализации: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.context:
                try:
                    pages = list(self.context.pages)
                    for page in pages:
                        try:
                            if page and not page.is_closed():
                                await asyncio.wait_for(page.close(), timeout=1.0)
                        except Exception:
                            try:
                                if page:
                                    page.close()
                            except Exception:
                                pass
                except Exception:
                    pass
                
                try:
                    await asyncio.wait_for(self.context.close(), timeout=2.0)
                    await asyncio.sleep(0.3)
                except Exception:
                    try:
                        self.context.close()
                    except Exception:
                        pass
        except Exception:
            pass
        
        try:
            if self.browser:
                try:
                    await asyncio.wait_for(self.browser.close(), timeout=2.0)
                    await asyncio.sleep(0.3)
                except Exception:
                    try:
                        self.browser.close()
                    except Exception:
                        pass
        except Exception:
            pass
        
        try:
            if self.playwright:
                try:
                    await asyncio.wait_for(self.playwright.stop(), timeout=3.0)
                except Exception:
                    try:
                        self.playwright.stop()
                    except Exception:
                        pass
        except Exception:
            pass
        
        await asyncio.sleep(0.5)

    async def _create_browser(self) -> Browser:
        user_agent = self.user_agent_manager.get_user_agent()
        
        browser_args = [
            "--disable-blink-features=AutomationControlled",  # Скрывает автоматизацию
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-web-security",  # Отключает некоторые проверки безопасности
            "--disable-features=IsolateOrigins,site-per-process",  # Улучшает совместимость
            "--disable-site-isolation-trials",  # Дополнительная маскировка
        ]
        
        proxy_config = None
        
        USE_PROXY = False
        
        if USE_PROXY:
            bright_data_proxy = self.captcha_solver.get_proxy_config()
            if bright_data_proxy:
                proxy_config = bright_data_proxy
                print(f"[{self.source_name}] Используется Bright Data прокси: {bright_data_proxy.get('server', 'N/A')}")
                print(f"[{self.source_name}] Username: {bright_data_proxy.get('username', 'N/A')[:50]}...")
            else:
                proxy = self.proxy_manager.get_proxy()
                if proxy:
                    proxy_host, proxy_port = proxy.split(":") if ":" in proxy else (proxy, "8080")
                    proxy_config = {
                        "server": f"http://{proxy_host}:{proxy_port}",
                    }
                    print(f"[{self.source_name}] Используется прокси: {proxy_host}:{proxy_port}")
                else:
                    print(f"[{self.source_name}] ⚠ Прокси не настроен! Возможны блокировки и капчи.")
                    proxy_config = None
        else:
            print(f"[{self.source_name}] ⚠ Прокси временно отключен для теста. Возможны блокировки.")
            proxy_config = None
        
        browser = await self.playwright.chromium.launch(
            headless=True,
            args=browser_args,
            proxy=proxy_config,
            timeout=60000
        )
        
        self.context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Asia/Vladivostok",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        
        # Расширенная маскировка автоматизации
        await self.context.add_init_script("""
            // Скрываем webdriver флаг
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Маскируем плагины
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Маскируем языки
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });
            
            // Переопределяем permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Маскируем Chrome
            window.chrome = {
                runtime: {}
            };
            
            // Переопределяем getBattery если есть
            if (navigator.getBattery) {
                navigator.getBattery = undefined;
            }
        """)
        
        return browser

    async def _human_delay(self) -> None:
        if self.config.request_delay:
            low, high = self.config.request_delay
            await asyncio.sleep(random.uniform(low, high))

    async def _solve_captcha_if_present(self, page: Page) -> bool:
        if self.captcha_solver.get_proxy_config():
            return False
        
        try:
            recaptcha_v2 = await page.query_selector('iframe[src*="recaptcha"]')
            recaptcha_v3 = await page.query_selector('[data-sitekey]')
            hcaptcha = await page.query_selector('iframe[src*="hcaptcha"]')
            
            if recaptcha_v2 or recaptcha_v3 or hcaptcha:
                await asyncio.sleep(5)
                return True
            
        except Exception:
            pass
        
        return False

    async def _fetch(self, url: str, retry: int = 0) -> Optional[Page]:
        await self._human_delay()
        
        page = None
        try:
            if not self.context:
                return None
            
            page = await self.context.new_page()
            
            try:
                timeout_ms = max(self.config.page_load_timeout * 1000, 120000)
                print(f"[{self.source_name}] Загрузка: {url[:80]}...")
                
                response = await page.goto(
                    url,
                    wait_until="load",
                    timeout=timeout_ms
                )
                
                if response:
                    status = response.status
                    print(f"[{self.source_name}] Статус ответа: {status}")
                    if status >= 400:
                        print(f"[{self.source_name}] ⚠ Ошибка HTTP: {status}")
                        if page and not page.is_closed():
                            try:
                                await page.close()
                            except Exception:
                                pass
                        if retry < self.config.retry_attempts:
                            await asyncio.sleep(self.config.retry_delay * (retry + 1))
                            return await self._fetch(url, retry + 1)
                        return None
                
                print(f"[{self.source_name}] Страница загружена, ожидание контента...")
                # Имитация человеческого поведения: случайные движения мыши и прокрутка
                try:
                    await page.evaluate("""
                        // Случайная прокрутка для имитации чтения
                        window.scrollTo(0, Math.random() * 500);
                        setTimeout(() => {
                            window.scrollTo(0, Math.random() * 1000);
                        }, Math.random() * 1000);
                    """)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(3, 6))
                
                # Проверяем статус страницы
                page_title = await page.title()
                print(f"[{self.source_name}] Заголовок страницы: {page_title[:60]}")
                
                # Проверяем на капчу
                captcha_selectors = [
                    "iframe[src*='recaptcha']",
                    "iframe[src*='hcaptcha']",
                    "div[class*='captcha']",
                ]
                has_captcha = False
                for selector in captcha_selectors:
                    captcha = await page.query_selector(selector)
                    if captcha:
                        print(f"[{self.source_name}] ⚠ Обнаружена капча: {selector}")
                        has_captcha = True
                        break
                
                captcha_solved = await self._solve_captcha_if_present(page)
                if captcha_solved or has_captcha:
                    print(f"[{self.source_name}] Ожидание решения капчи...")
                    await asyncio.sleep(5)
                
                return page
                
            except PlaywrightTimeoutError:
                print(f"[{self.source_name}] Таймаут загрузки страницы (попытка {retry + 1}/{self.config.retry_attempts})")
                if retry < self.config.retry_attempts:
                    if page and not page.is_closed():
                        try:
                            await page.close()
                        except Exception:
                            pass
                    await asyncio.sleep(self.config.retry_delay * (retry + 1))
                    return await self._fetch(url, retry + 1)
                if page and not page.is_closed():
                    try:
                        await page.close()
                    except Exception:
                        pass
                print(f"[{self.source_name}] Не удалось загрузить страницу после {self.config.retry_attempts} попыток")
                return None
                
        except Exception as e:
            print(f"[{self.source_name}] Ошибка при загрузке страницы: {str(e)[:100]}")
            if page and not page.is_closed():
                try:
                    await page.close()
                except Exception:
                    pass
            if retry < self.config.retry_attempts:
                await asyncio.sleep(self.config.retry_delay * (retry + 1))
                return await self._fetch(url, retry + 1)
            return None

    @abstractmethod
    async def parse_listing_page(self, url: str) -> Optional[Listing]:
        pass

    @abstractmethod
    async def parse_listings_page(self, page: int = 1) -> List[Listing]:
        pass

    @abstractmethod
    def get_base_url(self) -> str:
        pass

    async def parse_all(self, max_pages: int = 10) -> List[Listing]:
        all_listings = []
        
        try:
            for page_num in range(1, max_pages + 1):
                try:
                    print(f"[{self.source_name}] Страница {page_num}/{max_pages}...", end=" ", flush=True)
                    listings = await self.parse_listings_page(page_num)
                    
                    if not listings:
                        print(f"объявлений не найдено")
                        if page_num == 1:
                            print(f"[{self.source_name}] Предупреждение: первая страница пустая, возможно проблема с парсингом")
                        break
                    
                    valid_listings = []
                    invalid_count = 0
                    invalid_reasons = {"price": 0, "area": 0, "rooms": 0, "keywords": 0, "empty": 0}
                    
                    for listing in listings:
                        if self.validator.validate(listing):
                            valid_listings.append(listing)
                        else:
                            invalid_count += 1
                            # Диагностика причин отклонения
                            if not listing.external_id or not listing.title or not listing.url:
                                invalid_reasons["empty"] += 1
                            elif not (self.config.min_price <= listing.price <= self.config.max_price):
                                invalid_reasons["price"] += 1
                            elif not (self.config.min_area <= listing.area <= self.config.max_area):
                                invalid_reasons["area"] += 1
                            elif not (self.config.min_rooms <= listing.rooms <= self.config.max_rooms):
                                invalid_reasons["rooms"] += 1
                            else:
                                invalid_reasons["keywords"] += 1
                            
                            # Показываем пример первого отклоненного объявления
                            if invalid_count == 1:
                                print(f"\n[{self.source_name}] Пример отклоненного объявления:")
                                print(f"  Цена: {listing.price} (диапазон: {self.config.min_price}-{self.config.max_price})")
                                print(f"  Площадь: {listing.area} (диапазон: {self.config.min_area}-{self.config.max_area})")
                                print(f"  Комнаты: {listing.rooms} (диапазон: {self.config.min_rooms}-{self.config.max_rooms})")
                                print(f"  Заголовок: {listing.title[:60]}...")
                    
                    all_listings.extend(valid_listings)
                    print(f"найдено {len(listings)} объявлений, валидных: {len(valid_listings)}")
                    if invalid_count > 0:
                        print(f"  Отклонено: {invalid_reasons}")
                    
                    await self._human_delay()
                    
                except Exception as e:
                    import traceback
                    print(f"ошибка: {str(e)[:100]}")
                    print(f"[{self.source_name}] Детали ошибки на странице {page_num}:")
                    traceback.print_exc()
                    continue
            
            print(f"[{self.source_name}] Всего собрано: {len(all_listings)} объявлений")
            return all_listings
        except Exception as e:
            import traceback
            print(f"[{self.source_name}] Критическая ошибка в parse_all: {e}")
            traceback.print_exc()
            return []
