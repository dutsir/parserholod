from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    canonical_title = Column(String(500), nullable=False, index=True)
    canonical_address = Column(String(500), index=True)
    district = Column(String(100), index=True)
    description = Column(Text)
    rooms = Column(Integer, index=True)
    area = Column(Float, index=True)
    property_type = Column(String(100), index=True)
    image_url = Column(String(1000))
    min_price = Column(Integer, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    offers = relationship("Offer", back_populates="product", cascade="all, delete-orphan")
    attributes = relationship("Attribute", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_products_search', 'canonical_title', 'canonical_address'),
        Index('ix_products_price_area', 'min_price', 'area'),
    )

class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    external_id = Column(String(100), nullable=False, index=True)
    website_name = Column(String(50), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    price = Column(Integer, nullable=False, index=True)
    url = Column(String(1000), nullable=False, unique=True)
    address = Column(String(500))
    district = Column(String(100), index=True)
    area = Column(Float)
    rooms = Column(Integer)
    property_type = Column(String(100))
    description = Column(Text)
    image_url = Column(String(1000))
    date_parsed = Column(DateTime, default=datetime.now, index=True)

    product = relationship("Product", back_populates="offers")

    __table_args__ = (
        Index('ix_offers_website_external', 'website_name', 'external_id'),
        Index('ix_offers_product_website', 'product_id', 'website_name'),
    )

class Attribute(Base):
    __tablename__ = "attributes"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_name = Column(String(200), nullable=False, index=True)
    attribute_value = Column(String(500), nullable=False)

    product = relationship("Product", back_populates="attributes")

    __table_args__ = (
        Index('ix_attributes_product_name', 'product_id', 'attribute_name'),
    )
