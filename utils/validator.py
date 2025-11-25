from typing import Optional
from models import Listing
from config import Config

class Validator:

    def __init__(self, config: Config):
        self.config = config

    def _has_excluded_keywords(self, text: Optional[str]) -> bool:
        if not text:
            return False
        lower = text.lower()
        return any(word in lower for word in self.config.exclude_keywords)

    def validate(self, listing: Listing) -> bool:
        if not listing.external_id or not listing.title or not listing.url:
            return False

        if self._has_excluded_keywords(listing.title) or self._has_excluded_keywords(listing.description):
            return False

        if not (self.config.min_price <= listing.price <= self.config.max_price):
            return False

        if not (self.config.min_area <= listing.area <= self.config.max_area):
            return False

        if not (self.config.min_rooms <= listing.rooms <= self.config.max_rooms):
            return False

        return True
