







DROP TABLE IF EXISTS attributes CASCADE;
DROP TABLE IF EXISTS offers CASCADE;
DROP TABLE IF EXISTS products CASCADE;






CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    canonical_title VARCHAR(500) NOT NULL,
    canonical_address VARCHAR(500),
    district VARCHAR(100),
    description TEXT,
    rooms INTEGER,
    area FLOAT,
    property_type VARCHAR(100),
    image_url VARCHAR(1000),
    min_price INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE INDEX idx_products_canonical_title ON products(canonical_title);
CREATE INDEX idx_products_canonical_address ON products(canonical_address);
CREATE INDEX idx_products_district ON products(district);
CREATE INDEX idx_products_rooms ON products(rooms);
CREATE INDEX idx_products_area ON products(area);
CREATE INDEX idx_products_property_type ON products(property_type);
CREATE INDEX idx_products_min_price ON products(min_price);
CREATE INDEX idx_products_created_at ON products(created_at);


CREATE INDEX ix_products_search ON products(canonical_title, canonical_address);


CREATE INDEX ix_products_price_area ON products(min_price, area);


COMMENT ON TABLE products IS 'Уникальные объекты недвижимости после дедупликации';
COMMENT ON COLUMN products.id IS 'Уникальный идентификатор продукта';
COMMENT ON COLUMN products.canonical_title IS 'Нормализованное название объекта';
COMMENT ON COLUMN products.canonical_address IS 'Нормализованный адрес объекта';
COMMENT ON COLUMN products.district IS 'Район города (например, "Фрунзенский")';
COMMENT ON COLUMN products.min_price IS 'Минимальная цена среди всех предложений';






CREATE TABLE offers (
    id SERIAL PRIMARY KEY,
    product_id INTEGER,
    external_id VARCHAR(100) NOT NULL,
    website_name VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    price INTEGER NOT NULL,
    url VARCHAR(1000) NOT NULL UNIQUE,
    address VARCHAR(500),
    district VARCHAR(100),
    area FLOAT,
    rooms INTEGER,
    property_type VARCHAR(100),
    description TEXT,
    image_url VARCHAR(1000),
    date_parsed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    

    CONSTRAINT fk_offers_product 
        FOREIGN KEY (product_id) 
        REFERENCES products(id) 
        ON DELETE CASCADE
);


CREATE INDEX idx_offers_product_id ON offers(product_id);
CREATE INDEX idx_offers_external_id ON offers(external_id);
CREATE INDEX idx_offers_website_name ON offers(website_name);
CREATE INDEX idx_offers_price ON offers(price);
CREATE INDEX idx_offers_date_parsed ON offers(date_parsed);
CREATE INDEX idx_offers_url ON offers(url);
CREATE INDEX idx_offers_district ON offers(district);


CREATE INDEX ix_offers_website_external ON offers(website_name, external_id);


CREATE INDEX ix_offers_product_website ON offers(product_id, website_name);


COMMENT ON TABLE offers IS 'Все объявления с различных сайтов';
COMMENT ON COLUMN offers.id IS 'Уникальный идентификатор предложения';
COMMENT ON COLUMN offers.product_id IS 'Связь с продуктом (может быть NULL до дедупликации)';
COMMENT ON COLUMN offers.external_id IS 'ID объявления на сайте-источнике';
COMMENT ON COLUMN offers.website_name IS 'Название сайта (avito, cian, farpost)';
COMMENT ON COLUMN offers.url IS 'URL объявления (уникальный)';
COMMENT ON COLUMN offers.district IS 'Район города (например, "Фрунзенский")';
COMMENT ON COLUMN offers.date_parsed IS 'Дата и время парсинга объявления';






CREATE TABLE attributes (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    attribute_name VARCHAR(200) NOT NULL,
    attribute_value VARCHAR(500) NOT NULL,
    

    CONSTRAINT fk_attributes_product 
        FOREIGN KEY (product_id) 
        REFERENCES products(id) 
        ON DELETE CASCADE
);


CREATE INDEX idx_attributes_product_id ON attributes(product_id);
CREATE INDEX idx_attributes_name ON attributes(attribute_name);


CREATE INDEX ix_attributes_product_name ON attributes(product_id, attribute_name);


COMMENT ON TABLE attributes IS 'Дополнительные характеристики объектов недвижимости';
COMMENT ON COLUMN attributes.id IS 'Уникальный идентификатор атрибута';
COMMENT ON COLUMN attributes.product_id IS 'Связь с продуктом';
COMMENT ON COLUMN attributes.attribute_name IS 'Название характеристики (например, "Этаж", "Тип дома")';
COMMENT ON COLUMN attributes.attribute_value IS 'Значение характеристики';





CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_products_updated_at 
    BEFORE UPDATE ON products 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();





CREATE OR REPLACE FUNCTION update_product_min_price()
RETURNS TRIGGER AS $$
BEGIN

    UPDATE products 
    SET min_price = (
        SELECT MIN(price) 
        FROM offers 
        WHERE product_id = COALESCE(NEW.product_id, OLD.product_id)
    )
    WHERE id = COALESCE(NEW.product_id, OLD.product_id);
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_min_price_on_offer_change
    AFTER INSERT OR UPDATE OR DELETE ON offers
    FOR EACH ROW
    EXECUTE FUNCTION update_product_min_price();






DO $$
BEGIN
    RAISE NOTICE 'Миграция 001 завершена успешно';
    RAISE NOTICE 'Созданы таблицы: products, offers, attributes';
    RAISE NOTICE 'Созданы индексы и триггеры';
END $$;

