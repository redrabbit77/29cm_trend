# 데이터 모델 상세 설계

## 1. 엔티티 관계도 (ERD)

```
┌─────────────┐
│ categories  │
│─────────────│
│ id (PK)     │
│ name        │
│ gender      │
└──────┬──────┘
       │
       │ 1:N
       │
┌──────▼──────────┐      ┌──────────────┐
│ collection_tasks│      │   products   │
│────────────────│      │──────────────│
│ id (PK)        │      │ id (PK)       │
│ category_id(FK)│◄─────┤ category_id   │
│ status         │      │ brand_id (FK) │
│ progress       │      │ name          │
└────────────────┘      │ price         │
                        │ size          │
┌──────────────┐        │ color         │
│   brands     │        │ description   │
│──────────────│        │ ranking       │
│ id (PK)      │◄───────┤ product_url   │
│ name         │  1:N   │ collected_at  │
└──────────────┘        └──────┬────────┘
                               │
                               │ 1:N
                               │
                        ┌──────▼──────────────┐
                        │  product_images     │
                        │─────────────────────│
                        │ id (PK)             │
                        │ product_id (FK)      │
                        │ image_url           │
                        │ image_type          │
                        │ order_index         │
                        └─────────────────────┘
```

## 2. 테이블 상세 스펙

### 2.1 categories 테이블

**목적**: 상품 카테고리 정보 저장

**컬럼**:
- `id` (UUID, PK): 카테고리 고유 ID
- `name` (VARCHAR(50), NOT NULL, UNIQUE): 카테고리명 ('의류', '가방', '슈즈', '액세서리', '주얼리')
- `gender` (VARCHAR(10), NOT NULL): 성별 ('여성', '남성')
- `created_at` (TIMESTAMP): 생성 시간
- `updated_at` (TIMESTAMP): 수정 시간

**인덱스**:
- `idx_categories_name`: name 컬럼 인덱스

**초기 데이터**:
```sql
INSERT INTO categories (name, gender) VALUES
('의류', '여성'),
('가방', '여성'),
('슈즈', '여성'),
('액세서리', '여성'),
('주얼리', '여성'),
('의류', '남성'),
('가방', '남성'),
('슈즈', '남성'),
('액세서리', '남성'),
('주얼리', '남성');
```

### 2.2 brands 테이블

**목적**: 브랜드 정보 저장

**컬럼**:
- `id` (UUID, PK): 브랜드 고유 ID
- `name` (VARCHAR(100), NOT NULL, UNIQUE): 브랜드명
- `created_at` (TIMESTAMP): 생성 시간
- `updated_at` (TIMESTAMP): 수정 시간

**인덱스**:
- `idx_brands_name`: name 컬럼 인덱스

### 2.3 products 테이블

**목적**: 수집된 상품 정보 저장

**컬럼**:
- `id` (UUID, PK): 상품 고유 ID
- `brand_id` (UUID, FK → brands.id): 브랜드 ID
- `category_id` (UUID, FK → categories.id): 카테고리 ID
- `name` (VARCHAR(500), NOT NULL): 상품명
- `price` (INTEGER, NOT NULL): 가격 (원 단위)
- `size` (TEXT): 사이즈 정보 (JSON 배열 형태, 예: '["S", "M", "L"]')
- `color` (TEXT): 색상 정보 (JSON 배열 형태, 예: '["블랙", "화이트"]')
- `description` (TEXT): 상세 설명 텍스트
- `ranking` (INTEGER): BEST 랭킹 (1-10)
- `product_url` (TEXT): 29CM 상품 페이지 URL
- `collected_at` (TIMESTAMP): 수집 시간
- `created_at` (TIMESTAMP): 생성 시간
- `updated_at` (TIMESTAMP): 수정 시간

**인덱스**:
- `idx_products_brand_id`: brand_id 컬럼 인덱스
- `idx_products_category_id`: category_id 컬럼 인덱스
- `idx_products_collected_at`: collected_at 컬럼 인덱스
- `idx_products_price`: price 컬럼 인덱스 (필터링 최적화)

**제약조건**:
- `ranking`은 1-10 사이의 값만 허용
- `price`는 0 이상의 값만 허용

### 2.4 product_images 테이블

**목적**: 상품 이미지 정보 저장

**컬럼**:
- `id` (UUID, PK): 이미지 고유 ID
- `product_id` (UUID, FK → products.id, ON DELETE CASCADE): 상품 ID
- `image_url` (TEXT, NOT NULL): Supabase Storage URL
- `image_type` (VARCHAR(20), DEFAULT 'lookbook'): 이미지 타입 ('lookbook', 'detail', 'thumbnail')
- `order_index` (INTEGER, DEFAULT 0): 이미지 순서
- `created_at` (TIMESTAMP): 생성 시간

**인덱스**:
- `idx_product_images_product_id`: product_id 컬럼 인덱스
- `idx_product_images_order`: (product_id, order_index) 복합 인덱스

### 2.5 collection_tasks 테이블

**목적**: 데이터 수집 작업 상태 관리

**컬럼**:
- `id` (UUID, PK): 작업 고유 ID
- `category_id` (UUID, FK → categories.id, ON DELETE CASCADE): 카테고리 ID
- `status` (VARCHAR(20), NOT NULL, DEFAULT 'pending'): 작업 상태 ('pending', 'running', 'completed', 'failed', 'cancelled')
- `progress` (INTEGER, DEFAULT 0): 진행률 (0-100)
- `total_items` (INTEGER, DEFAULT 0): 총 수집할 항목 수
- `collected_items` (INTEGER, DEFAULT 0): 수집 완료된 항목 수
- `error_message` (TEXT): 에러 발생 시 메시지
- `started_at` (TIMESTAMP): 작업 시작 시간
- `completed_at` (TIMESTAMP): 작업 완료 시간
- `created_at` (TIMESTAMP): 생성 시간
- `updated_at` (TIMESTAMP): 수정 시간

**인덱스**:
- `idx_collection_tasks_status`: status 컬럼 인덱스
- `idx_collection_tasks_category_id`: category_id 컬럼 인덱스
- `idx_collection_tasks_created_at`: created_at 컬럼 인덱스

**상태 전이**:
```
pending → running → completed
                ↓
             failed
                ↓
            cancelled
```

## 3. Pydantic 모델 정의

### 3.1 Category 모델

```python
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class Category(BaseModel):
    id: UUID
    name: str = Field(..., max_length=50)
    gender: str = Field(..., pattern="^(여성|남성)$")
    created_at: datetime
    updated_at: datetime

class CategoryCreate(BaseModel):
    name: str = Field(..., max_length=50)
    gender: str = Field(..., pattern="^(여성|남성)$")
```

### 3.2 Brand 모델

```python
class Brand(BaseModel):
    id: UUID
    name: str = Field(..., max_length=100)
    created_at: datetime
    updated_at: datetime

class BrandCreate(BaseModel):
    name: str = Field(..., max_length=100)
```

### 3.3 Product 모델

```python
from typing import List, Optional

class Product(BaseModel):
    id: UUID
    brand_id: UUID
    category_id: UUID
    name: str = Field(..., max_length=500)
    price: int = Field(..., ge=0)
    size: Optional[List[str]] = None
    color: Optional[List[str]] = None
    description: Optional[str] = None
    ranking: Optional[int] = Field(None, ge=1, le=10)
    product_url: Optional[str] = None
    collected_at: datetime
    created_at: datetime
    updated_at: datetime

class ProductCreate(BaseModel):
    brand_id: UUID
    category_id: UUID
    name: str = Field(..., max_length=500)
    price: int = Field(..., ge=0)
    size: Optional[List[str]] = None
    color: Optional[List[str]] = None
    description: Optional[str] = None
    ranking: Optional[int] = Field(None, ge=1, le=10)
    product_url: Optional[str] = None
```

### 3.4 ProductImage 모델

```python
class ProductImage(BaseModel):
    id: UUID
    product_id: UUID
    image_url: str
    image_type: str = Field(default="lookbook", pattern="^(lookbook|detail|thumbnail)$")
    order_index: int = Field(default=0, ge=0)
    created_at: datetime

class ProductImageCreate(BaseModel):
    product_id: UUID
    image_url: str
    image_type: str = Field(default="lookbook", pattern="^(lookbook|detail|thumbnail)$")
    order_index: int = Field(default=0, ge=0)
```

### 3.5 CollectionTask 모델

```python
class CollectionTask(BaseModel):
    id: UUID
    category_id: UUID
    status: str = Field(..., pattern="^(pending|running|completed|failed|cancelled)$")
    progress: int = Field(default=0, ge=0, le=100)
    total_items: int = Field(default=0, ge=0)
    collected_items: int = Field(default=0, ge=0)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class CollectionTaskCreate(BaseModel):
    category_id: UUID

class CollectionTaskUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(pending|running|completed|failed|cancelled)$")
    progress: Optional[int] = Field(None, ge=0, le=100)
    total_items: Optional[int] = Field(None, ge=0)
    collected_items: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = None
```

## 4. 데이터 정규화

### 4.1 정규화 수준
- **3NF (Third Normal Form)** 준수
- 중복 데이터 최소화
- 참조 무결성 보장

### 4.2 비정규화 고려사항
- `products.size`와 `products.color`는 JSON 배열로 저장 (조회 성능 향상)
- 통계 쿼리 최적화를 위한 뷰(View) 생성 고려

## 5. 데이터 마이그레이션

### 5.1 초기 마이그레이션 스크립트

```sql
-- categories 테이블 생성
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    gender VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- brands 테이블 생성
CREATE TABLE IF NOT EXISTS brands (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- products 테이블 생성
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand_id UUID REFERENCES brands(id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    price INTEGER NOT NULL CHECK (price >= 0),
    size TEXT,
    color TEXT,
    description TEXT,
    ranking INTEGER CHECK (ranking >= 1 AND ranking <= 10),
    product_url TEXT,
    collected_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- product_images 테이블 생성
CREATE TABLE IF NOT EXISTS product_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    image_type VARCHAR(20) DEFAULT 'lookbook',
    order_index INTEGER DEFAULT 0 CHECK (order_index >= 0),
    created_at TIMESTAMP DEFAULT NOW()
);

-- collection_tasks 테이블 생성
CREATE TABLE IF NOT EXISTS collection_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    total_items INTEGER DEFAULT 0 CHECK (total_items >= 0),
    collected_items INTEGER DEFAULT 0 CHECK (collected_items >= 0),
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_products_brand_id ON products(brand_id);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_collected_at ON products(collected_at);
CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);
CREATE INDEX IF NOT EXISTS idx_product_images_product_id ON product_images(product_id);
CREATE INDEX IF NOT EXISTS idx_product_images_order ON product_images(product_id, order_index);
CREATE INDEX IF NOT EXISTS idx_collection_tasks_status ON collection_tasks(status);
CREATE INDEX IF NOT EXISTS idx_collection_tasks_category_id ON collection_tasks(category_id);
CREATE INDEX IF NOT EXISTS idx_collection_tasks_created_at ON collection_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_brands_name ON brands(name);
CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name);

-- 초기 카테고리 데이터 삽입
INSERT INTO categories (name, gender) VALUES
('의류', '여성'),
('가방', '여성'),
('슈즈', '여성'),
('액세서리', '여성'),
('주얼리', '여성'),
('의류', '남성'),
('가방', '남성'),
('슈즈', '남성'),
('액세서리', '남성'),
('주얼리', '남성')
ON CONFLICT (name) DO NOTHING;
```

## 6. RLS (Row Level Security) 정책

### 6.1 익명 읽기 허용
```sql
-- 모든 테이블에 대해 익명 사용자 읽기 허용
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE brands ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE collection_tasks ENABLE ROW LEVEL SECURITY;

-- 읽기 정책
CREATE POLICY "Allow anonymous read" ON categories FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON brands FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON products FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON product_images FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON collection_tasks FOR SELECT USING (true);
```

### 6.2 서비스 역할 쓰기 허용
```sql
-- 서비스 역할을 통한 쓰기만 허용 (서버 사이드)
-- 이는 Supabase 서비스 키를 사용하여 수행됨
```

## 7. 데이터 백업 전략

### 7.1 자동 백업
- Supabase Free Tier의 자동 백업 활용
- 일일 백업 보관

### 7.2 수동 백업
- 중요 데이터는 주기적으로 CSV로 내보내기
- 이미지는 Supabase Storage에서 직접 다운로드
