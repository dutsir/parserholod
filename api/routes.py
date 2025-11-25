from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_db
from database.crud import CRUDProduct, CRUDOffer
from api.schemas import (
    ProductResponse,
    ProductDetailResponse,
    SearchResponse,
    StatsResponse,
    OfferResponse
)

router = APIRouter()

@router.get("/search", response_model=SearchResponse)
async def search_listings(
    q: str = Query("", description="Поисковый запрос"),
    min_price: Optional[int] = Query(None, description="Минимальная цена"),
    max_price: Optional[int] = Query(None, description="Максимальная цена"),
    min_area: Optional[float] = Query(None, description="Минимальная площадь"),
    max_area: Optional[float] = Query(None, description="Максимальная площадь"),
    rooms: Optional[int] = Query(None, description="Количество комнат"),
    property_type: Optional[str] = Query(None, description="Тип недвижимости"),
    district: Optional[str] = Query(None, description="Район (например, 'Фрунзенский')"),
    limit: int = Query(50, ge=1, le=200, description="Количество результатов"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    db: AsyncSession = Depends(get_db)
):
    products = await CRUDProduct.search(
        db,
        query=q,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
        rooms=rooms,
        property_type=property_type,
        district=district,
        limit=limit,
        offset=offset
    )

    total = await CRUDProduct.count(db)

    return SearchResponse(
        results=[ProductResponse.from_orm(p) for p in products],
        total=total,
        limit=limit,
        offset=offset
    )

@router.get("/listings", response_model=List[ProductResponse])
async def get_all_listings(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    products = await CRUDProduct.get_all(db, limit=limit, offset=offset)
    return [ProductResponse.from_orm(p) for p in products]

@router.get("/listing/{product_id}", response_model=ProductDetailResponse)
async def get_listing_detail(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    product = await CRUDProduct.get_by_id(db, product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    return ProductDetailResponse.from_orm(product)

@router.get("/product/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получение детальной информации о продукте и всех предложениях на него.

    Возвращает:
    - Основную информацию о продукте (название, адрес, описание)
    - Все предложения с разных сайтов
    - Дополнительные атрибуты (характеристики)
    """
    product = await CRUDProduct.get_by_id(db, product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")

    return ProductDetailResponse.from_orm(product)

@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_products = await CRUDProduct.count(db)
    offers_by_source = await CRUDOffer.count_by_source(db)

    return StatsResponse(
        total_products=total_products,
        total_offers=sum(offers_by_source.values()),
        offers_by_source=offers_by_source
    )
