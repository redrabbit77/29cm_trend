# 기술 구현 계획: 29CM 데이터 수집 엔진

## 1. 시스템 아키텍처 개요

### 1.1 하이브리드 아키텍처
본 시스템은 세 가지 주요 컴포넌트로 구성됩니다:

```
┌─────────────────────────────────────────────────────────┐
│              Web Control Plane (Streamlit)              │
│  - 사용자 인터페이스                                    │
│  - 작업 요청 생성                                        │
│  - 데이터 시각화                                        │
└──────────────────┬──────────────────────────────────────┘
                   │ Supabase Realtime
                   │ (상태 동기화)
┌──────────────────▼──────────────────────────────────────┐
│              Central DB (Supabase)                      │
│  - PostgreSQL (데이터 저장)                              │
│  - Storage (이미지 저장)                                 │
│  - Realtime (상태 동기화)                                │
└──────────────────┬──────────────────────────────────────┘
                   │ Supabase Realtime
                   │ (작업 감지)
┌──────────────────▼──────────────────────────────────────┐
│         Local Execution Plane (Playwright Agent)         │
│  - 작업 감지 및 실행                                      │
│  - 브라우저 자동화                                        │
│  - 데이터 수집                                           │
│  - 이미지 저장 및 업로드                                   │
└─────────────────────────────────────────────────────────┘
```

### 1.2 컴포넌트 간 통신 흐름

1. **작업 생성**: Streamlit → Supabase `collection_tasks` 테이블 INSERT
2. **작업 감지**: Local Agent → Supabase Realtime 구독
3. **상태 업데이트**: Local Agent → `collection_tasks` 테이블 UPDATE
4. **데이터 저장**: Local Agent → `products`, `product_images` 테이블 INSERT
5. **이미지 업로드**: Local Agent → Supabase Storage
6. **UI 업데이트**: Streamlit → Supabase Realtime 구독으로 실시간 상태 표시

## 2. 데이터 모델 설계

### 2.1 데이터베이스 스키마

#### 2.1.1 `categories` 테이블
```sql
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,  -- '의류', '가방', '슈즈', '액세서리', '주얼리'
    gender VARCHAR(10) NOT NULL,        -- '여성', '남성'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 2.1.2 `brands` 테이블
```sql
CREATE TABLE brands (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 2.1.3 `products` 테이블
```sql
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand_id UUID REFERENCES brands(id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    price INTEGER NOT NULL,                    -- 원 단위
    size TEXT,                                 -- JSON 배열 형태로 저장
    color TEXT,                                -- JSON 배열 형태로 저장
    description TEXT,                          -- 상세 설명 텍스트
    ranking INTEGER,                           -- BEST 랭킹 (1-10)
    product_url TEXT,                          -- 29CM 상품 페이지 URL
    collected_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_products_brand_id ON products(brand_id);
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_products_collected_at ON products(collected_at);
```

#### 2.1.4 `product_images` 테이블
```sql
CREATE TABLE product_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,                   -- Supabase Storage URL
    image_type VARCHAR(20) DEFAULT 'lookbook', -- 'lookbook', 'detail', etc.
    order_index INTEGER DEFAULT 0,            -- 이미지 순서
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_product_images_product_id ON product_images(product_id);
```

#### 2.1.5 `collection_tasks` 테이블
```sql
CREATE TABLE collection_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    progress INTEGER DEFAULT 0,                -- 0-100
    total_items INTEGER DEFAULT 0,              -- 총 수집할 항목 수
    collected_items INTEGER DEFAULT 0,          -- 수집 완료된 항목 수
    error_message TEXT,                         -- 에러 발생 시 메시지
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_collection_tasks_status ON collection_tasks(status);
CREATE INDEX idx_collection_tasks_category_id ON collection_tasks(category_id);
```

### 2.2 Supabase Storage 구조

```
storage/
└── product-images/
    ├── {product_id}/
    │   ├── lookbook_001.jpg
    │   ├── lookbook_002.jpg
    │   └── ...
```

## 3. 컴포넌트 설계

### 3.1 Web Control Plane (Streamlit)

#### 3.1.1 디렉토리 구조
```
web/
├── app.py                 # 메인 Streamlit 앱
├── pages/
│   ├── dashboard.py      # 대시보드 페이지
│   ├── collection.py     # 수집 관리 페이지
│   └── visualization.py  # 브랜드 맵 시각화 페이지
├── components/
│   ├── task_status.py    # 작업 상태 컴포넌트
│   ├── data_table.py     # 데이터 테이블 컴포넌트
│   └── brand_map.py      # 브랜드 맵 컴포넌트
├── services/
│   ├── supabase_client.py    # Supabase 클라이언트
│   └── data_service.py       # 데이터 조회 서비스
└── utils/
    └── config.py         # 설정 관리
```

#### 3.1.2 주요 기능 모듈

**app.py**
- Streamlit 메인 앱 진입점
- 페이지 라우팅
- 사이드바 네비게이션

**pages/collection.py**
- 카테고리 선택 UI
- 수집 작업 생성
- 작업 상태 모니터링 (Realtime)
- 작업 목록 표시

**pages/dashboard.py**
- 수집된 데이터 테이블 뷰
- 필터링 및 정렬 기능
- 데이터 내보내기 (CSV, Excel)
- 통계 정보 표시

**pages/visualization.py**
- 브랜드 맵 시각화
- 축 설정 UI
- 인터랙티브 차트 (Plotly)
- 브랜드 상세 정보 팝업

**services/supabase_client.py**
- Supabase 클라이언트 초기화
- Realtime 구독 관리
- 공통 쿼리 메서드

### 3.2 Local Execution Plane (Playwright Agent)

#### 3.2.1 디렉토리 구조
```
agent/
├── main.py                # 에이전트 메인 진입점
├── collector/
│   ├── __init__.py
│   ├── task_monitor.py    # Supabase 작업 감지
│   ├── browser_manager.py # 브라우저 관리
│   ├── scraper.py         # 메인 스크래핑 로직
│   └── human_behavior.py  # 인간 행동 모사
├── utils/
│   ├── bezier.py          # 베지어 곡선 알고리즘
│   ├── image_handler.py   # 이미지 저장 및 업로드
│   └── config.py          # 설정 관리
└── services/
    ├── supabase_client.py # Supabase 클라이언트
    └── data_service.py    # 데이터 저장 서비스
```

#### 3.2.2 주요 기능 모듈

**main.py**
- 에이전트 초기화
- Supabase Realtime 구독 시작
- 작업 감지 및 실행 루프

**collector/task_monitor.py**
- Supabase Realtime 구독
- `collection_tasks` 테이블 변경 감지
- 새 작업 큐에 추가

**collector/browser_manager.py**
- Playwright 브라우저 인스턴스 관리
- 브라우저 컨텍스트 생성 및 관리
- User-Agent 로테이션
- 쿠키 및 세션 관리

**collector/scraper.py**
- 29CM 웹사이트 네비게이션
- BEST 상품 목록 페이지 파싱
- 상품 상세 페이지 방문 및 데이터 수집
- 에러 처리 및 재시도 로직

**collector/human_behavior.py**
- 베지어 곡선 기반 마우스 이동
- 텍스트 선택 및 복사 (드래그 → Ctrl+C)
- 이미지 저장 시뮬레이션 (우클릭 → 'V' 키)
- 랜덤 딜레이 및 불규칙한 행동 패턴

**utils/bezier.py**
- 베지어 곡선 생성 알고리즘
- 자연스러운 마우스 경로 생성

**utils/image_handler.py**
- 로컬 이미지 저장
- Supabase Storage 업로드
- 이미지 메타데이터 관리

### 3.3 Shared 모듈

#### 3.3.1 디렉토리 구조
```
shared/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── product.py         # Product Pydantic 모델
│   ├── brand.py           # Brand Pydantic 모델
│   ├── task.py            # Task Pydantic 모델
│   └── category.py        # Category Pydantic 모델
└── config/
    └── settings.py        # 공통 설정 (Pydantic Settings)
```

## 4. API 설계

### 4.1 Supabase 클라이언트 API

#### 4.1.1 작업 관리 API
```python
# 작업 생성
def create_collection_task(category_id: UUID) -> dict

# 작업 상태 업데이트
def update_task_status(task_id: UUID, status: str, progress: int = None) -> dict

# 작업 목록 조회
def get_tasks(status: str = None) -> List[dict]

# 작업 상세 조회
def get_task(task_id: UUID) -> dict
```

#### 4.1.2 데이터 조회 API
```python
# 상품 목록 조회 (필터링, 정렬 지원)
def get_products(
    brand_id: UUID = None,
    category_id: UUID = None,
    min_price: int = None,
    max_price: int = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "collected_at",
    order_desc: bool = True
) -> List[dict]

# 브랜드 목록 조회
def get_brands() -> List[dict]

# 카테고리 목록 조회
def get_categories() -> List[dict]

# 브랜드별 통계 조회
def get_brand_statistics() -> List[dict]
```

#### 4.1.3 이미지 관리 API
```python
# 이미지 업로드
def upload_image(file_path: str, product_id: UUID, image_type: str = "lookbook") -> str

# 상품 이미지 목록 조회
def get_product_images(product_id: UUID) -> List[dict]
```

### 4.2 Realtime 구독 API

```python
# 작업 상태 변경 구독
def subscribe_to_tasks(callback: Callable) -> None

# 작업 상태 변경 구독 해제
def unsubscribe_from_tasks() -> None
```

## 5. 인간 행동 모사 알고리즘 상세

### 5.1 베지어 곡선 마우스 이동

```python
def generate_bezier_path(start: Tuple[int, int], end: Tuple[int, int], 
                        control_points: List[Tuple[int, int]] = None,
                        num_points: int = 50) -> List[Tuple[int, int]]:
    """
    베지어 곡선을 따라 마우스 경로 생성
    - 시작점과 끝점 사이에 랜덤한 제어점 생성
    - 자연스러운 곡선 경로 생성
    """
    pass

def move_mouse_human_like(start: Tuple[int, int], end: Tuple[int, int]):
    """
    인간처럼 자연스러운 마우스 이동
    - 베지어 곡선 경로 생성
    - 각 포인트마다 랜덤 딜레이 추가
    """
    pass
```

### 5.2 텍스트 수집 시뮬레이션

```python
def extract_text_by_selection(element_selector: str) -> str:
    """
    텍스트 선택 및 복사 시뮬레이션
    1. 요소로 마우스 이동 (베지어 곡선)
    2. 마우스 드래그로 텍스트 선택
    3. Ctrl+C 입력
    4. pyperclip로 클립보드 내용 가져오기
    5. 랜덤 딜레이
    """
    pass
```

### 5.3 이미지 저장 시뮬레이션

```python
def save_image_human_like(image_element_selector: str, save_path: str):
    """
    이미지 저장 시뮬레이션
    1. 이미지 요소로 마우스 이동
    2. 우클릭
    3. 'V' 키 입력 (이미지 저장 단축키)
    4. 파일명 입력 (랜덤 딜레이 포함)
    5. Enter 키 입력
    6. 파일 저장 대기
    """
    pass
```

### 5.4 랜덤 딜레이 및 행동 패턴

```python
def random_delay(min_seconds: float = 0.5, max_seconds: float = 2.0):
    """
    랜덤 딜레이 (인간의 불규칙한 행동 모사)
    """
    pass

def random_scroll():
    """
    랜덤 스크롤 (페이지 탐색 시뮬레이션)
    """
    pass

def random_mouse_movement():
    """
    랜덤 마우스 움직임 (활성 상태 유지)
    """
    pass
```

## 6. 구현 단계별 계획

### Phase 1: 기반 구조 구축 (Week 1)

#### 1.1 프로젝트 설정
- [ ] Git 저장소 초기화
- [ ] 가상 환경 설정
- [ ] 의존성 설치 및 requirements.txt 확인
- [ ] 환경 변수 설정 (.env 파일)
- [ ] Supabase 프로젝트 생성 및 설정

#### 1.2 데이터베이스 스키마 구축
- [ ] Supabase에서 테이블 생성 (SQL 마이그레이션)
- [ ] RLS (Row Level Security) 정책 설정
- [ ] Storage 버킷 생성 및 정책 설정
- [ ] 초기 데이터 삽입 (카테고리 데이터)

#### 1.3 공유 모듈 개발
- [ ] Pydantic 모델 정의 (Product, Brand, Category, Task)
- [ ] 공통 설정 모듈 (Pydantic Settings)
- [ ] Supabase 클라이언트 래퍼 클래스

### Phase 2: Web Control Plane 개발 (Week 2)

#### 2.1 기본 UI 구조
- [ ] Streamlit 메인 앱 구조
- [ ] 페이지 라우팅 설정
- [ ] 사이드바 네비게이션

#### 2.2 수집 관리 페이지
- [ ] 카테고리 선택 UI
- [ ] 작업 생성 기능
- [ ] 작업 목록 표시
- [ ] Realtime 작업 상태 업데이트

#### 2.3 대시보드 페이지
- [ ] 데이터 테이블 뷰
- [ ] 필터링 기능 (브랜드, 카테고리, 가격)
- [ ] 정렬 기능
- [ ] 데이터 내보내기 (CSV, Excel)

### Phase 3: Local Agent 개발 (Week 3-4)

#### 3.1 브라우저 관리
- [ ] Playwright 브라우저 인스턴스 관리
- [ ] User-Agent 로테이션
- [ ] 쿠키 및 세션 관리

#### 3.2 작업 감지 시스템
- [ ] Supabase Realtime 구독 구현
- [ ] 작업 큐 관리
- [ ] 작업 실행 스케줄러

#### 3.3 인간 행동 모사 모듈
- [ ] 베지어 곡선 알고리즘 구현
- [ ] 마우스 이동 시뮬레이션
- [ ] 텍스트 선택 및 복사 시뮬레이션
- [ ] 이미지 저장 시뮬레이션
- [ ] 랜덤 딜레이 및 행동 패턴

#### 3.4 스크래핑 로직
- [ ] 29CM BEST 페이지 파싱
- [ ] 상품 상세 페이지 방문
- [ ] 데이터 추출 (브랜드명, 상품명, 가격, 사이즈, 색상, 설명)
- [ ] 이미지 URL 추출 및 다운로드
- [ ] 에러 처리 및 재시도 로직

#### 3.5 데이터 저장
- [ ] Supabase에 데이터 저장
- [ ] 이미지 업로드 (Supabase Storage)
- [ ] 작업 상태 업데이트

### Phase 4: 시각화 기능 개발 (Week 5)

#### 4.1 브랜드 맵 시각화
- [ ] Plotly 인터랙티브 차트 구현
- [ ] 축 설정 UI (가격, 컨셉, 무드 등)
- [ ] 브랜드 포인트 표시
- [ ] 브랜드 클릭 시 상세 정보 팝업
- [ ] 줌 및 팬 기능

#### 4.2 통계 대시보드
- [ ] 브랜드별 통계
- [ ] 카테고리별 통계
- [ ] 가격 분포 차트
- [ ] 수집 현황 요약

### Phase 5: 테스팅 및 최적화 (Week 6)

#### 5.1 단위 테스트
- [ ] 인간 행동 모사 모듈 테스트
- [ ] 데이터 추출 로직 테스트
- [ ] Supabase 클라이언트 테스트

#### 5.2 통합 테스트
- [ ] 전체 수집 워크플로우 테스트
- [ ] Web-Agent-DB 통합 테스트
- [ ] Realtime 동기화 테스트

#### 5.3 성능 최적화
- [ ] 데이터베이스 쿼리 최적화
- [ ] 이미지 업로드 배치 처리
- [ ] 메모리 사용량 최적화

#### 5.4 봇 탐지 회피 테스트
- [ ] 다양한 시나리오에서 봇 탐지 회피 테스트
- [ ] 성공률 측정 및 개선

## 7. 기술 스택 상세

### 7.1 Python 패키지

**웹 프레임워크**
- `streamlit>=1.28.0`: 웹 UI 프레임워크
- `streamlit-aggrid>=0.3.0`: 고급 데이터 그리드 (선택사항)

**데이터베이스**
- `supabase>=2.0.0`: Supabase Python 클라이언트
- `postgrest>=0.13.0`: PostgreSQL REST API 클라이언트

**브라우저 자동화**
- `playwright>=1.40.0`: 브라우저 자동화
- `playwright-stealth>=1.0.6`: 스텔스 모드 (선택사항)

**인간 행동 모사**
- `pyautogui>=0.9.54`: 마우스/키보드 제어
- `pyperclip>=1.8.2`: 클립보드 관리
- `numpy>=1.24.0`: 베지어 곡선 계산 (선택사항)

**데이터 처리**
- `pandas>=2.0.0`: 데이터 처리 및 분석
- `pydantic>=2.0.0`: 데이터 검증 및 설정 관리

**시각화**
- `plotly>=5.17.0`: 인터랙티브 차트
- `matplotlib>=3.7.0`: 정적 차트 (선택사항)

**유틸리티**
- `python-dotenv>=1.0.0`: 환경 변수 관리
- `httpx>=0.25.0`: HTTP 클라이언트
- `rich>=13.0.0`: 콘솔 출력 포맷팅

**테스팅**
- `pytest>=7.4.0`: 테스트 프레임워크
- `pytest-asyncio>=0.21.0`: 비동기 테스트
- `pytest-playwright>=0.4.0`: Playwright 테스트

### 7.2 개발 도구

- **버전 관리**: Git
- **코드 포맷팅**: `black`, `isort`
- **린팅**: `pylint`, `mypy`
- **타입 체킹**: `mypy`
- **문서화**: Markdown

## 8. 보안 고려사항

### 8.1 API 키 관리
- 모든 Supabase 키는 환경 변수로 관리
- `.env` 파일은 `.gitignore`에 포함
- 프로덕션 환경에서는 환경 변수 또는 시크릿 관리 서비스 사용

### 8.2 데이터베이스 보안
- RLS (Row Level Security) 정책 설정
- 서비스 역할 키는 서버 사이드에서만 사용
- 익명 키는 클라이언트 사이드에서만 사용

### 8.3 웹 스크래핑 윤리
- robots.txt 준수
- 적절한 요청 간격 유지
- 29CM 이용약관 준수
- 개인정보 수집 금지

## 9. 배포 계획

### 9.1 Web Control Plane 배포
- **플랫폼**: Streamlit Community Cloud
- **배포 방법**: GitHub 연동 자동 배포
- **환경 변수**: Streamlit Cloud 대시보드에서 설정

### 9.2 Local Agent 배포
- **플랫폼**: 로컬 PC
- **실행 방법**: Python 스크립트 직접 실행 또는 서비스로 등록
- **자동 시작**: Windows Task Scheduler 또는 systemd 사용

### 9.3 데이터베이스
- **플랫폼**: Supabase Free Tier
- **백업**: Supabase 자동 백업 활용

## 10. 모니터링 및 로깅

### 10.1 로깅 전략
- **로컬 에이전트**: 파일 기반 로깅 (`logs/` 디렉토리)
- **웹 앱**: Streamlit 로깅 활용
- **로그 레벨**: INFO, WARNING, ERROR
- **로그 포맷**: 구조화된 JSON 로그 (선택사항)

### 10.2 모니터링
- **작업 상태**: Supabase `collection_tasks` 테이블 모니터링
- **에러 추적**: 로그 파일 분석
- **성능 메트릭**: 작업 완료 시간, 성공률 추적

## 11. 개발 프로세스

### 11.1 TDD 기반 개발
- 모든 기능은 테스트 먼저 작성
- 테스트 통과 후 구현
- 리팩토링 시 테스트 유지

### 11.2 Git 워크플로우
- **작업 단위**: 각 기능별로 커밋
- **커밋 메시지**: 명확하고 설명적인 메시지
- **브랜치 전략**: main 브랜치 + feature 브랜치

### 11.3 작업 노트 관리
- 각 작업 완료 후 `docs/work-notes/` 디렉토리에 마크다운 파일로 정리
- 작업 내용, 이슈, 해결 방법 기록

## 12. 리스크 및 대응 방안

### 12.1 기술적 리스크

**리스크 1: 봇 탐지 시스템**
- **확률**: 중간
- **영향**: 높음
- **대응**: 인간 행동 모사 알고리즘 강화, 다양한 우회 기법 적용

**리스크 2: 웹사이트 구조 변경**
- **확률**: 높음
- **영향**: 중간
- **대응**: 유연한 셀렉터 사용, 정기적인 모니터링

**리스크 3: Supabase Free Tier 제한**
- **확률**: 낮음
- **영향**: 중간
- **대응**: 데이터 최적화, 스토리지 사용량 모니터링

### 12.2 운영 리스크

**리스크 4: 로컬 에이전트 중단**
- **확률**: 중간
- **영향**: 높음
- **대응**: 자동 재시작 메커니즘, 상태 복구 로직

**리스크 5: 네트워크 불안정**
- **확률**: 중간
- **영향**: 중간
- **대응**: 재시도 로직, 오프라인 큐 관리

## 13. 성공 지표

### 13.1 기능적 지표
- 모든 카테고리에서 BEST 1~10위 상품 데이터 수집 성공률: 95% 이상
- 데이터 수집 완료 시간: 카테고리당 10분 이내
- 웹 UI 응답 시간: 2초 이내

### 13.2 비기능적 지표
- 봇 탐지 시스템 우회 성공률: 90% 이상
- 데이터베이스 쿼리 응답 시간: 500ms 이내
- 이미지 업로드 성공률: 95% 이상

### 13.3 사용자 경험 지표
- 작업 생성부터 완료까지의 전체 워크플로우 성공률: 90% 이상
- 사용자 에러 발생률: 5% 이하
