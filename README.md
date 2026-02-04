# 29CM 브랜드 포지셔닝 맵 구축을 위한 데이터 수집 엔진

## 프로젝트 개요

29CM의 감도 높은 큐레이션 데이터를 바탕으로 시장 내 브랜드들의 포지션을 분석하기 위한 데이터 수집 및 분석 시스템입니다.

## 주요 기능

- **Human-like Scraping**: 29CM 웹사이트에서 사람처럼 행동하며 데이터 수집
- **데이터 관리**: Supabase를 통한 중앙 집중식 데이터 저장 및 관리
- **시각화 대시보드**: Streamlit 기반 웹 인터페이스로 데이터 조회 및 브랜드 맵 시각화

## 기술 스택

- **언어**: Python 3.10+
- **웹 인터페이스**: Streamlit
- **데이터베이스**: Supabase (PostgreSQL)
- **수집 엔진**: Playwright
- **인간 행위 모사**: PyAutoGUI, pyperclip

## 프로젝트 구조

```
.
├── .specify/              # Speckit 프로젝트 설정
│   ├── memory/            # 프로젝트 원칙 및 메모리
│   └── specs/             # 기능 스펙
├── web/                   # Streamlit 웹 애플리케이션
├── agent/                 # 로컬 데이터 수집 에이전트
├── shared/                # 공유 유틸리티 및 모델
├── PRD.md                 # 제품 요구사항 문서
├── TRD.md                 # 기술 명세서
└── requirements.txt       # Python 의존성
```

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. Supabase 데이터베이스 설정

1. [Supabase](https://supabase.com)에서 새 프로젝트를 생성합니다.
2. Supabase 대시보드의 SQL Editor로 이동합니다.
3. `supabase/sql/initial_schema.sql` 파일의 내용을 복사하여 SQL Editor에 붙여넣고 실행합니다.
4. Storage에서 `product-images` 버킷을 생성합니다 (선택사항, 이미지 업로드 시 필요).

### 3. 환경 변수 설정

`.env.example` 파일을 참고하여 `.env` 파일을 생성하고 다음 변수를 설정합니다:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_key
SUPABASE_STORAGE_BUCKET=product-images
LOCAL_IMAGE_DIR=images
LOG_DIR=logs
```

**Supabase 키 찾기:**
- `SUPABASE_URL`: 프로젝트 설정 > API > Project URL
- `SUPABASE_KEY`: 프로젝트 설정 > API > Project API keys > `anon` `public` 키
- `SUPABASE_SERVICE_KEY`: 프로젝트 설정 > API > Project API keys > `service_role` `secret` 키

### 3. 실행 (단일 실행 구조)

**웹 앱만 실행하면 됩니다.** 별도의 에이전트 터미널을 켤 필요 없습니다.

```bash
# 프로젝트 루트에서
streamlit run web/app.py
```

브라우저에서 **데이터 수집 관리** 페이지로 이동한 뒤, **전체 수집** 또는 **카테고리별 수집**을 선택하고 **PDF 수집 시작**을 누르면 백그라운드에서 PDF 수집이 실행됩니다. 같은 페이지에서 진행 상황 로그를 확인할 수 있습니다.

### PDF 수집 (BEST → 카테고리별 1~10위 → A5 PDF)

29cm 방문 → 베스트 메뉴 클릭 → 각 카테고리 페이지 → 1~10위 상품 상세 페이지를 **A5 PDF**로 저장:

```bash
# 프로젝트 루트에서 (기본: pdfs/ 폴더에 저장)
python -m agent.run_pdf_collect

# 저장 폴더 지정
python -m agent.run_pdf_collect --output pdfs

# 카테고리 1개만 수집
python -m agent.run_pdf_collect --category 여성_의류

# 브라우저 창 숨김
python -m agent.run_pdf_collect --headless
```

저장 구조: `pdfs/{카테고리명}/{01~10}_{상품ID}.pdf` (인쇄 용지 A5).

### PDF 분석 (상품 정보 구조화)

수집된 PDF에서 텍스트를 추출해 **상품명·브랜드·가격·소재·케어·사이즈·사이즈_상세·색상** 등을 구조화합니다. **OPENAI_API_KEY**를 `.env`에 설정하면 **LLM**(gpt-4o-mini)으로 추출(권장), 미설정 또는 실패 시 규칙 기반 폴백.

```bash
# .env에 OPENAI_API_KEY 설정 후 → LLM으로 추출
python scripts/analyze_pdfs.py

# LLM 없이 규칙 기반만
python scripts/analyze_pdfs.py --no-llm

# 특정 폴더만 / 개수 제한
python scripts/analyze_pdfs.py pdfs/여성_의류 --limit 5
python scripts/analyze_pdfs.py --output data/my_analysis
```

**결과 확인:**
- **웹**: Streamlit 실행 후 **좌측 사이드바**에서 **「PDF 분석 결과」** 페이지 선택 → 표로 확인. (먼저 같은 페이지에서 **「PDF 분석 실행」** 버튼으로 분석 실행)
- **파일**: `data/pdf_analysis/pdf_products.json`, `data/pdf_analysis/pdf_products.csv` 에 저장됨.

상세: `docs/pdf-analysis-feasibility.md`.

### 데이터 전체 초기화 (전면 개편용)

Supabase의 수집·상품·이미지 데이터를 **모두 삭제**할 때:

```bash
# 프로젝트 루트에서 (실제 삭제)
python -m scripts.reset_supabase_all

# 삭제 예정만 확인
python -m scripts.reset_supabase_all --dry-run

# 카테고리까지 비우기 (재시드 시 initial_schema.sql 실행 필요)
python -m scripts.reset_supabase_all --include-categories
```

삭제 대상: `product_images` → `products` → `collection_tasks` → `brands` (FK 순서), Storage 버킷(`product-images`) 내 객체. `categories`는 기본적으로 유지(앱 동작용).

**데이터가 그대로 남아 있으면** Supabase 대시보드 **SQL Editor**에서 아래 파일 내용을 붙여 넣고 실행하세요 (TRUNCATE로 한 번에 비움):

- `supabase_local/sql/truncate_all_data.sql`

## 구현 진행 상황

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 1 | 공통 구조, 설정, 데이터 모델, Supabase 클라이언트 | ✅ 완료 |
| Phase 2 | Streamlit 앱, 수집 관리·대시보드·브랜드 맵 페이지 | ✅ 완료 |
| Phase 3 | PDF 수집 에이전트(Playwright), 베스트 카테고리별 1~10위 상품 상세 페이지 A5 PDF 저장 | ✅ 완료 |
| Phase 4 | 브랜드 맵 고도화, 컨셉 스코어, 통계 대시보드 | ⏳ 대기 |
| Phase 5 | 테스팅, 최적화, 봇 회피 검증 | ⏳ 대기 |

상세: `docs/work-notes/phase1-completion.md`, `phase2-completion.md`, `phase3-progress.md`

## 개발 가이드

이 프로젝트는 **Spec-Driven Development** 방식으로 개발됩니다. 자세한 내용은 `.specify/` 디렉토리를 참조하세요.

### Speckit 워크플로우

1. **프로젝트 원칙 설정**: `.specify/memory/constitution.md`
2. **스펙 작성**: `.specify/specs/001-29cm-data-collection/spec.md`
3. **기술 구현 계획**: `/speckit.plan` 명령 사용
4. **작업 목록 생성**: `/speckit.tasks` 명령 사용
5. **구현**: `/speckit.implement` 명령 사용

## 라이선스

MIT License
