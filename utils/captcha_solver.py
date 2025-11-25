import aiohttp
from typing import Optional
from config import Config

class CaptchaSolver:
    def __init__(self, config: Config):
        self.config = config
        self.api_key = getattr(config, 'bright_data_api_key', None)
        self.api_url = getattr(config, 'bright_data_api_url', 'https://api.brightdata.com/request')
        self.zone = getattr(config, 'bright_data_zone', 'web_unlocker1')

    def get_proxy_config(self) -> Optional[dict]:
        if not self.api_key:
            return None

        api_key = self.api_key.strip()

        if '-' in api_key:
            parts = api_key.split('-', 1)
            if len(parts) == 2 and len(parts[0]) < 20:
                customer_id = parts[0]
                zone_password = parts[1]
            else:

                customer_id = None
                zone_password = api_key
        else:
            customer_id = None
            zone_password = api_key

        if customer_id:
            username = f"brd-customer-{customer_id}-zone-{self.zone}"
        else:

            username = f"brd-customer-zone-{self.zone}"

        config = {
            "server": "http://zproxy.lum-superproxy.io:22225",
            "username": username,
            "password": zone_password
        }

        return config

    async def unlock_url(self, url: str) -> Optional[str]:
        if not self.api_key:
            return None

        async with aiohttp.ClientSession() as session:
            payload = {
                "zone": self.zone,
                "url": url,
                "format": "raw"
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            try:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    return None
            except Exception:
                return None

    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> Optional[str]:
        return None

    async def solve_recaptcha_v3(self, site_key: str, page_url: str, action: str = "submit") -> Optional[str]:
        return None

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> Optional[str]:
        return None

    async def solve_image_captcha(self, image_base64: str) -> Optional[str]:
        return None
