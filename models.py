from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class Listing:
    external_id: str
    title: str
    price: int
    url: str
    address: str
    area: float
    rooms: int
    property_type: str
    source: str
    parsed_at: datetime = field(default_factory=datetime.now)

    description: Optional[str] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    images: Optional[List[str]] = None
    district: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "external_id": self.external_id,
            "title": self.title,
            "price": self.price,
            "url": self.url,
            "address": self.address,
            "area": self.area,
            "rooms": self.rooms,
            "property_type": self.property_type,
            "source": self.source,
            "parsed_at": self.parsed_at.isoformat(),
            "description": self.description,
            "floor": self.floor,
            "total_floors": self.total_floors,
            "images": self.images or [],
        }
