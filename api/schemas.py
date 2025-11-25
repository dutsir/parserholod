from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict

class OfferResponse(BaseModel):
    id: int
    website_name: str
    title: str
    price: int
    url: str
    address: str
    district: Optional[str] = None
    area: float
    rooms: int
    property_type: str
    date_parsed: datetime

    model_config = ConfigDict(from_attributes=True)

class AttributeResponse(BaseModel):
    attribute_name: str
    attribute_value: str

    model_config = ConfigDict(from_attributes=True)

class ProductResponse(BaseModel):
    id: int
    canonical_title: str
    canonical_address: str
    district: Optional[str] = None
    rooms: int
    area: float
    property_type: str
    min_price: int
    image_url: Optional[str] = None
    offers_count: int = 0

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, product):
        return cls(
            id=product.id,
            canonical_title=product.canonical_title,
            canonical_address=product.canonical_address or "",
            district=product.district,
            rooms=product.rooms,
            area=product.area,
            property_type=product.property_type,
            min_price=product.min_price or 0,
            image_url=product.image_url,
            offers_count=len(product.offers) if hasattr(product, 'offers') else 0
        )

class ProductDetailResponse(BaseModel):
    id: int
    canonical_title: str
    canonical_address: str
    district: Optional[str] = None
    description: Optional[str] = None
    rooms: int
    area: float
    property_type: str
    min_price: int
    image_url: Optional[str] = None
    created_at: datetime
    offers: List[OfferResponse] = []
    attributes: List[AttributeResponse] = []

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, product):
        return cls(
            id=product.id,
            canonical_title=product.canonical_title,
            canonical_address=product.canonical_address or "",
            district=product.district,
            description=product.description,
            rooms=product.rooms,
            area=product.area,
            property_type=product.property_type,
            min_price=product.min_price or 0,
            image_url=product.image_url,
            created_at=product.created_at,
            offers=[OfferResponse.from_orm(o) for o in product.offers],
            attributes=[AttributeResponse.from_orm(a) for a in product.attributes]
        )

class SearchResponse(BaseModel):
    results: List[ProductResponse]
    total: int
    limit: int
    offset: int

class StatsResponse(BaseModel):
    total_products: int
    total_offers: int
    offers_by_source: Dict[str, int]
