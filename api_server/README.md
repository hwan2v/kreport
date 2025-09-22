# API Server (FastAPI)
## 1. 프로젝트 개요
이 서버는 HTML/TSV 문서를 추출 -> 변환 -> 인덱싱 -> 검색하는 파이프라인을 제공합니다.
도메인 계층과 어댑터 계층을 분리한 구조(헥사고날 아키텍처)로, 데이터 소스/검색엔진 교체에 유연합니다.
- 주요 기능
  - POST /v1/extract : 원천 데이터(HTML/TSV) 추출 및 저장
  - POST /v1/transform : 정규화/정제/스키마 변환
  - POST /v1/index : OpenSearch 색인
  - POST /v1/search : 색인 데이터 검색
  - GET /health : 상태 점검
- 문서
  - Swagger UI: /docs
    - http://localhost:8000/docs
  - ReDoc: /redoc
    - http://localhost:8000/redoc
  - OpenAPI: /openapi.json
- 테스트
  - pytest (unit / integration 분리)

## 2. 실행 방법
### 1) Docker, Docker Compose 설치
#### Ubuntu / Debian
```bash
# 패키지 업데이트
sudo apt update

# Docker & Compose 플러그인 설치
sudo apt install -y docker.io docker-compose-plugin

# 서비스 시작 및 부팅 시 자동 시작
sudo systemctl enable --now docker

# 설치 확인
docker --version
docker compose version
```

#### CentOS / RHEL / Fedora
```bash
# Docker 엔진 설치
sudo dnf install -y docker

# 서비스 시작 및 부팅 시 자동 시작
sudo systemctl enable --now docker

# 설치 확인
docker --version
docker compose version
```
#### macOS
```bash
# 1) Docker Desktop 다운로드 & 설치
# https://www.docker.com/products/docker-desktop/

# 2) 설치 후 버전 확인
docker --version
docker compose version
```

### 2) Docker Compose 실행
```bash
# 루트에서
docker compose up -d --build

# 실행 후 확인
docker compose ps

# 다음 컨테이너가 실행되어야 함
kreport-k-api-1
kreport-opensearch-1
kreport-python-1
```

## 3. 프로젝트 구조
```
api_server/app
├── adapters        # I/O 어댑터: fetchers, parsers, transformers, indexers, searchers
├── api             # FastAPI 라우터(/v1/routers/*), DI(deps.py)
├── domain          # 모델, 포트(인터페이스), 서비스(핵심 로직)
├── middlewares     # 요청 컨텍스트/로그
├── platform        # 설정/에러/로깅 공통 인프라
├── resources       # 수집 데이터/스키마
└── tests           # 테스트코드
```
- adapters: 외부 자원 접근(파일, OpenSearch 등)과 포맷 처리(HTML/TSV 파싱, 변환)
- domain.services: 비즈니스 로직 집약부 (예: search_service.py, index_service.py)
- api.routers: 실제 HTTP 엔드포인트 (extract/index/search/transform/health)
- tests: unit / integration 분리, pytest로 실행

### 환경 설정
```
OPENSEARCH_HOST: 오픈서치 주소 (ex. http://opensearch:9200)
OPENSEARCH_INDEX: 인덱스 프리픽스 (ex. collection)
OPENSEARCH_ALIAS: 인덱스 별칭 (ex. kakaobank)
```

## 5. API 요약
### Extract
```
POST /v1/extract
Body:
{
  "source": "all" | "html" | "tsv",
  "date": "3"  // 내부 규칙 문자열 (예: 3일 차 데이터)
}
200 OK -> {"success": true, "message": "...", "data": {"html": {...}, "tsv": {...}}}
```

### Transform
```
POST /v1/transform
Body:
{
  "source": "all" | "html" | "tsv",
  "date": "3"
}
200 OK -> {"success": true, "message": "...", "data": {"html": {...}, "tsv": {...}}}
```

### Index
```
POST /v1/index
Body:
{
  "source": "all" | "html" | "tsv",
  "date": "3"
}
200 OK -> {"success": true, "message": "...", "data": {"html": {...}, "tsv": {...}}}
```

### Search
```
POST /v1/search
Body:
{
  "query": "카카오뱅크",
  "size": 3,
  "explain": false
}
200 OK -> {
  "success": true,
  "message": "검색 성공",
  "data": {
    "total": 134,
    "took_ms": 42,
    "items": [
      {"id":"...", "score":12.3, "title":"..."}
    ]
  }
}
```
## 6. 데이터 경로
- root
  - api_server/resources/data/
- html
  - html/day_{1..3}/*.html             : 수집 문서 (원본)
  - html/day_{1..3}/*_parsed.json      : 추출 문서 (extract 호출시 생성)
  - html/day_{1..3}/*_normalized.json  : 색인 문서 (transform 호출시 생성)
- tsv
  - tsv/day_{1..3}/qna.tsv             : 수집 문서 (원본)
  - tsv/day_{1..3}/*_parsed.json       : 추출 문서 (extract 호출시 생성)
  - tsv/day_{1..3}/*_normalized.json   : 색인 문서 (transform 호출시 생성)
- index schema
  - api_server/resources/schema/search_index.json (색인 매핑 참고)

## 7. 테스트
###  단위/통합 테스트 실행
```
## 로컬에서
python -m pip install -r requirements.txt
pytest -q

## 컨테이너에서
docker exec -it kreport-k-api-1 bash
pytest -q
```

### 특정 스위트 실행
```
pytest api_server/tests/unit -q
pytest api_server/tests/integration -q
```

## 8. 빠른 검증용 curl
```bash
# Health
curl -s http://localhost:8000/health

# Extract (전체)
curl -s -X POST http://localhost:8000/extract -H 'Content-Type: application/json' \
  -d '{"date":"3"}'

# Transform (HTML만)
curl -s -X POST http://localhost:8000/transform -H 'Content-Type: application/json' \
  -d '{"source":"html","date":"3"}'

# Index (TSV만)
curl -s -X POST http://localhost:8000/index -H 'Content-Type: application/json' \
  -d '{"source":"tsv","date":"3"}'

# Search
curl -s -X POST http://localhost:8000/search -H 'Content-Type: application/json' \
  -d '{"query":"카카오뱅크"}'

```


## 9. 풀이 방법 및 의사 결정 근거거
### 과제 해석
  - HTML/TSV 데이터를 수집/가공/검색하는 end-to-end 파이프라인 구축 요구사항으로 이해했습니다.
  - 단순 실행 결과보다 구조적 설계와 확장성을 중점적으로 고려했습니다.

### 접근 방법
  - 전체 흐름을 `Extract → Transform → Index → Search` 4단계로 나누어 설계했습니다.
  - 각 단계는 독립된 API로 제공하여 재사용성과 테스트 용이성을 높였습니다.

### 의사 결정 근거
   - **FastAPI**: 빠른 개발, 타입 기반 검증, Swagger 자동 문서화를 위해 선택
   - **OpenSearch**: BM25 검색 성능, 확장성, 오픈소스 라이선스
   - **헥사고날 구조**: adapters/domain/services 분리로 외부 의존성 교체 용이
   - **Docker Compose**: API 서버 + OpenSearch + Logstash를 한번에 실행할 수 있도록 구성
### 제한 및 선택
   - 시간 관계상 보안/인증은 구현하지 않았으나, `security/guards.py` 위치에 확장 가능성을 고려
   - 리포트 생성은 단일 스크립트(`report_app`)로 단순화하여 핵심 로직에 집중


### FastAPI 채택
- 개발 생산성과 성능(ASGI), 자동 Swagger 문서, 타입 기반 검증을 위해 선택


- 헥사고날 구조
  - domain(핵심 로직)과 adapters(I/O) 분리 → OpenSearch ↔ 다른 검색엔진 교체 용이
- 단계 분리
  - (Extract→Transform→Index→Search): 파이프라인 가시성/테스트 용이성 확보
- OpenSearch
  - BM25 기본 검색 품질, 스케일아웃, 라이선스 이슈 적음
- 테스트 전략
  - 단위/통합 분리로 회귀 방지, 파이프라인 변경 시 영향 최소화
- 문서화(스웨거 강화)
  - response_model, 예시(examples), operation_id로 채점자/리뷰어의 이해 비용↓
- 데이터 표준화
  - *_parsed.json/*_normalized.json 계층을 둬 인덱스 스키마 준수 & 추후 확장에 대비
