from typing import List, Optional
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Product, Offer, Attribute
from models import Listing

class CRUDProduct:

    @staticmethod
    async def create(db: AsyncSession, title: str, address: str, district: str = None, **kwargs) -> Product:
        product = Product(
            canonical_title=title,
            canonical_address=address,
            district=district,
            **kwargs
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product

    @staticmethod
    async def get_by_id(db: AsyncSession, product_id: int) -> Optional[Product]:
        result = await db.execute(
            select(Product)
            .options(selectinload(Product.offers), selectinload(Product.attributes))
            .where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def search(
        db: AsyncSession,
        query: str = "",
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        rooms: Optional[int] = None,
        property_type: Optional[str] = None,
        district: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Product]:
        # Важно: загружаем офферы через selectinload для доступа к ним
        stmt = select(Product).options(selectinload(Product.offers))

        if query:
            search_pattern = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Product.canonical_title).like(search_pattern),
                    func.lower(Product.canonical_address).like(search_pattern),
                    func.lower(Product.description).like(search_pattern)
                )
            )

        if min_price is not None:
            stmt = stmt.where(Product.min_price >= min_price)
        if max_price is not None:
            stmt = stmt.where(Product.min_price <= max_price)

        if min_area is not None:
            stmt = stmt.where(Product.area >= min_area)
        if max_area is not None:
            stmt = stmt.where(Product.area <= max_area)

        if rooms is not None:
            stmt = stmt.where(Product.rooms == rooms)

        if property_type:
            stmt = stmt.where(Product.property_type == property_type)

        if district:
            stmt = stmt.where(Product.district.ilike(f"%{district}%"))

        stmt = stmt.order_by(Product.min_price.asc()).limit(limit).offset(offset)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_all(db: AsyncSession, limit: int = 100, offset: int = 0) -> List[Product]:
        result = await db.execute(
            select(Product)
            .options(selectinload(Product.offers))
            .order_by(Product.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count(db: AsyncSession) -> int:
        result = await db.execute(select(func.count(Product.id)))
        return result.scalar_one()

    @staticmethod
    async def update_min_price(db: AsyncSession, product_id: int) -> None:
        result = await db.execute(
            select(func.min(Offer.price)).where(Offer.product_id == product_id)
        )
        min_price = result.scalar_one_or_none()
        if min_price:
            await db.execute(
                select(Product).where(Product.id == product_id)
            )
            product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one()
            product.min_price = min_price
            await db.commit()

class CRUDOffer:

    @staticmethod
    async def create(db: AsyncSession, listing: Listing, product_id: Optional[int] = None) -> Offer:
        offer = Offer(
            product_id=product_id,
            external_id=listing.external_id,
            website_name=listing.source,
            title=listing.title,
            price=listing.price,
            url=listing.url,
            address=listing.address,
            district=listing.district,
            area=listing.area,
            rooms=listing.rooms,
            property_type=listing.property_type,
            description=listing.description,
            image_url=listing.images[0] if listing.images else None
        )
        db.add(offer)
        await db.commit()
        await db.refresh(offer)
        return offer

    @staticmethod
    async def get_by_url(db: AsyncSession, url: str) -> Optional[Offer]:
        result = await db.execute(select(Offer).where(Offer.url == url))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_external_id(
        db: AsyncSession, external_id: str, website_name: str
    ) -> Optional[Offer]:
        result = await db.execute(
            select(Offer).where(
                and_(
                    Offer.external_id == external_id,
                    Offer.website_name == website_name
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_unassigned(db: AsyncSession, limit: int = 100) -> List[Offer]:
        result = await db.execute(
            select(Offer).where(Offer.product_id.is_(None)).limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_by_source(db: AsyncSession) -> dict:
        result = await db.execute(
            select(Offer.website_name, func.count(Offer.id))
            .group_by(Offer.website_name)
        )
        return {source: count for source, count in result.all()}

class CRUDAttribute:

    @staticmethod
    async def create(
        db: AsyncSession, product_id: int, name: str, value: str
    ) -> Attribute:
        attr = Attribute(
            product_id=product_id,
            attribute_name=name,
            attribute_value=value
        )
        db.add(attr)
        await db.commit()
        await db.refresh(attr)
        return attr

    @staticmethod
    async def bulk_create(
        db: AsyncSession, product_id: int, attributes: dict
    ) -> None:
        attrs = [
            Attribute(product_id=product_id, attribute_name=k, attribute_value=str(v))
            for k, v in attributes.items()
        ]
        db.add_all(attrs)
        await db.commit()
