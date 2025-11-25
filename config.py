from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import os


@dataclass
class Config:

    proxies: List[str] = field(default_factory=list)
    proxy_rotation: bool = True
    proxy_timeout: int = 10

    user_agents: List[str] = field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        ]
    )
    user_agent_rotation: bool = True

    request_delay: Tuple[int, int] = (2, 5)
    page_load_timeout: int = 120
    retry_attempts: int = 2
    retry_delay: int = 15

    min_price: int = 5000
    max_price: int = 100000000
    min_area: float = 10.0
    max_area: float = 500.0
    min_rooms: int = 1
    max_rooms: int = 10

    exclude_keywords: List[str] = field(
        default_factory=lambda: [
            "реклама",
            "акция",
            "скидка",
            "бесплатно",
            "тестовое",
            "test",
            "advertisement",
            "spam",
        ]
    )

    output_dir: str = "output"
    save_json: bool = True
    save_csv: bool = True

    enabled_sources: List[str] = field(default_factory=lambda: ["avito", "farpost"])

    max_concurrent_requests: int = 5

    log_level: str = "INFO"
    log_file: Optional[str] = "parser.log"

    bright_data_api_key: Optional[str] = None
    bright_data_api_url: str = "https://api.brightdata.com/request"
    bright_data_zone: str = "web_unlocker1"

    @classmethod
    def from_env(cls) -> "Config":
        config = cls()

        proxies_env = os.getenv("PROXIES")
        if proxies_env:
            config.proxies = [p.strip() for p in proxies_env.split(",") if p.strip()]

        user_agents_env = os.getenv("USER_AGENTS")
        if user_agents_env:
            config.user_agents = [ua.strip() for ua in user_agents_env.split(",") if ua.strip()]

        delay_env = os.getenv("REQUEST_DELAY")
        if delay_env and "-" in delay_env:
            min_delay, max_delay = map(int, delay_env.split("-"))
            config.request_delay = (min_delay, max_delay)

        output_dir = os.getenv("OUTPUT_DIR")
        if output_dir:
            config.output_dir = output_dir

        bright_data_key = os.getenv("BRIGHT_DATA_API_KEY")
        if bright_data_key:
            config.bright_data_api_key = bright_data_key

        bright_data_url = os.getenv("BRIGHT_DATA_API_URL")
        if bright_data_url:
            config.bright_data_api_url = bright_data_url

        bright_data_zone = os.getenv("BRIGHT_DATA_ZONE")
        if bright_data_zone:
            config.bright_data_zone = bright_data_zone

        return config

    def get_proxy_dict(self, proxy: Optional[str] = None) -> Optional[dict]:
        if not proxy:
            return None
        return {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}",
        }
