






ALTER TABLE products 
ADD COLUMN IF NOT EXISTS district VARCHAR(100);


ALTER TABLE offers 
ADD COLUMN IF NOT EXISTS district VARCHAR(100);


CREATE INDEX IF NOT EXISTS idx_products_district ON products(district);
CREATE INDEX IF NOT EXISTS idx_offers_district ON offers(district);


COMMENT ON COLUMN products.district IS 'Район города (например, "Фрунзенский")';
COMMENT ON COLUMN offers.district IS 'Район города (например, "Фрунзенский")';


DO $$
BEGIN
    RAISE NOTICE 'Миграция 002 завершена успешно';
    RAISE NOTICE 'Добавлен столбец district в таблицы products и offers';
END $$;

