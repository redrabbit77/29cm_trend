-- Supabase 데이터 전체 비우기 (테이블 구조는 유지, 데이터만 삭제)
-- Supabase 대시보드 > SQL Editor에서 이 스크립트를 실행하세요.
-- FK 순서: product_images → products → collection_tasks → brands → categories

TRUNCATE TABLE product_images RESTART IDENTITY CASCADE;
TRUNCATE TABLE products RESTART IDENTITY CASCADE;
TRUNCATE TABLE collection_tasks RESTART IDENTITY CASCADE;
TRUNCATE TABLE brands RESTART IDENTITY CASCADE;
TRUNCATE TABLE categories RESTART IDENTITY CASCADE;

-- categories 재시드 (앱에서 카테고리 선택 필요 시 아래 실행)
-- INSERT INTO categories (name, gender) VALUES
-- ('의류', '여성'), ('가방', '여성'), ('슈즈', '여성'), ('액세서리', '여성'), ('주얼리', '여성'),
-- ('의류', '남성'), ('가방', '남성'), ('슈즈', '남성'), ('액세서리', '남성'), ('주얼리', '남성')
-- ON CONFLICT (name) DO NOTHING;
