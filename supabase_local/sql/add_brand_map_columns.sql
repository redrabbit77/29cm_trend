-- 브랜드 맵 지표 컬럼 추가 (데이터 기반 맵 및 DB 저장용)
-- Supabase SQL Editor에서 실행하세요.

ALTER TABLE brands
  ADD COLUMN IF NOT EXISTS style_axis NUMERIC(5,2) CHECK (style_axis >= 0 AND style_axis <= 100),
  ADD COLUMN IF NOT EXISTS premium_axis NUMERIC(5,2) CHECK (premium_axis >= 0 AND premium_axis <= 100),
  ADD COLUMN IF NOT EXISTS representative_color VARCHAR(20);

COMMENT ON COLUMN brands.style_axis IS '브랜드맵 스타일 축 0~100 (0=클래식/페미닌, 100=시크·미니멀·스트릿)';
COMMENT ON COLUMN brands.premium_axis IS '브랜드맵 프리미엄 축 0~100 (0=데일리, 100=프리미엄)';
COMMENT ON COLUMN brands.representative_color IS '브랜드 표시색 (hex 예 #1a1a1a 또는 색상명)';
