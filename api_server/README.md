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

### 3) 시나리오 실행
```
# 추출 -> 변환 -> 색인 (date 1, 2, 3 반복 요청)
curl -s -X POST http://localhost:8000/v1/extract -H 'Content-Type: application/json' \
  -d '{"date":"1"}'

curl -s -X POST http://localhost:8000/v1/transform -H 'Content-Type: application/json' \
  -d '{"date":"1"}'

curl -s -X POST http://localhost:8000/v1/index -H 'Content-Type: application/json' \
  -d '{"date":"1"}'


# 검색
curl -s -X POST http://localhost:8000/v1/search -H 'Content-Type: application/json' \
  -d '{"query":"카카오뱅크"}'

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
curl -s -X POST http://localhost:8000/v1/extract -H 'Content-Type: application/json' \
  -d '{"date":"3"}'

# Transform (HTML만)
curl -s -X POST http://localhost:8000/v1/transform -H 'Content-Type: application/json' \
  -d '{"source":"html","date":"3"}'

# Index (TSV만)
curl -s -X POST http://localhost:8000/v1/index -H 'Content-Type: application/json' \
  -d '{"source":"tsv","date":"3"}'

# Search
curl -s -X POST http://localhost:8000/v1/search -H 'Content-Type: application/json' \
  -d '{"query":"카카오뱅크"}'

```


## 9. 풀이 방법 및 의사 결정 근거
### 과제 해석
이번 과제는 문서 추출과 검색 파이프라인 전반을 구현하는 것으로 이해했습니다.
여러 문서 타입(HTML, TSV)이 주어진 점에서, 다양한 형태의 문서를 파싱하고 검색에 적합하게 가공하는 시스템을 설계하는 것이 1차 목표라고 보았습니다.

2차 목표는 문서 타입별로 필요한 정보를 추출/적재하여 검색에 최적화된 데이터 구조를 만드는 것이었고,
마지막으로는 이를 바탕으로 검색 정확도를 높이기 위한 튜닝 작업을 진행하는 것을 3차 목표로 설정했습니다.



### 접근 방법
과제에 이미 수집된 문서가 있었지만, 실제 서비스라면 수집 링크 -> 문서 수집 -> 추출 -> 변환 -> 적재 -> 검색으로 이어지는 전체 파이프라인을 고려해야 한다고 보았습니다.
단순 계층형 구조로도 구현할 수 있었지만, 다양한 외부 연동(링크 수집, 문서 타입별 처리)과 확장성/유지보수를 고려했을 때 한계가 있다고 판단했습니다.
여러 문서 타입과 서비스가 연계되면 단일 파이프라인만으로는 부족하기 때문에 문서 타입별로 독립적인 파이프라인이 필요합니다. 또 핵심 로직이 자주 변경되면 사이드 이펙트와 재처리 비용이 커지므로, 핵심 코드를 외부 인프라(DB, API 등)와 분리하여 인터페이스(포트)를 통해서만 통신하도록 설계했습니다. 이를 통해 다양한 어댑터를 조합해 파이프라인을 유연하게 구성할 수 있고, 변경과 확장에 유리한 구조가 됩니다. 이런 이유로 헥사고날 아키텍처를 선택했습니다.


정보 추출에 대해서는 문서 타입에 따라 처리 방식을 달리했습니다.
HTML 문서는 하나의 문서를 그대로 검색 대상으로 삼는 반면, TSV 문서는 여러 개의 QnA 쌍으로 구성되어 있어 복수 문서를 생성해야 했습니다. HTML은 위키 기반의 서술형 콘텐츠, TSV는 질의응답형 콘텐츠라는 점에서 공통 필드를 정의하기 어려웠습니다. 다행히 필수 정보가 동일하지 않아도 된다는 조건이 있었기 때문에, TSV 문서의 경우 단순히 question과 answer 필드만 추출하고 변환하는 방식을 선택했습니다.

다음으로 published 필드를 활용하는 방식을 정의했습니다. TSV 문서에서는 색인 비용 절감을 위해 published=false인 문서는 아예 색인하지 않았고, 검색 옵션에서도 제외했습니다. 반면 HTML 위키 문서는 published=true를 기본값으로 두되, 차단이나 제재 같은 운영 이슈에 대비할 수 있도록 published 필드로 제어 가능하게 했습니다. 검색 쿼리 역시 published=true 조건을 고정으로 포함시켰습니다.

HTML 문서 구조는 부제목과 본문이 세로로 이어지는 형태로, 문서마다 부제목 위치나 구조가 달라 정형화된 템플릿으로 처리하기 어려웠습니다. 또한 일부 문서에는 요약이나 인포박스가 아예 없었습니다. 따라서 특정 셀렉터 기반 추출보다는 불필요한 태그를 제거하고, 의미 있는 부제목과 본문 텍스트를 최대한 보존하는 방식으로 처리했습니다. 그중 인포박스와 요약은 핵심 정보로 판단해 별도의 필드로 분리했고, 이후 검색 랭킹 보정 시 가중치를 높게 부여할 계획이었습니다. 변환 과정에서는 일부 정답 문서에서 발견된 소수점 표기 오류(둘째 자리 0 누락)도 보정했습니다.


검색 랭킹 튜닝 방식은 문서 타입별로 다르게 접근했습니다. TSV(QnA)의 경우 question과 answer 모두 동등하게 중요한 정보를 담고 있으므로 같은 가중치를 적용했습니다. 특정 질의에서는 핵심 단어가 겹쳐 ngram·edge_ngram 기반으로 매칭을 강화하려 했으나, 다른 질의에 부정적 영향을 주어 제거했습니다. BM25 파라미터(b, k1) 조정이나 품사 제거 실험도 동일한 이유로 적용하지 않았습니다. 결국 question, answer 필드만으로도 충분히 높은 정확도를 보였고, 일부 질의는 과감히 포기하는 선택을 했습니다.

HTML(위키) 문서는 인포박스와 요약을 별도 필드로 두고 높은 가중치를 부여했으며, 특히 인포박스는 두 번 점수를 반영하도록 설계했습니다. 또한 title은 짧고 핵심적인 키워드가 많아 높은 가중치를 주었습니다. 하지만 여전히 랭킹이 잘 정렬되지 않는 케이스가 있었고, BM25 파라미터 조정은 다른 질의에 악영향을 미쳐 제외했습니다. 대신 위키 문서 간 우열을 가릴 수 있는 간단한 피처를 도입했는데, 접근 가능한 텍스트 길이를 min-max 정규화하여 function_score에 반영했습니다. 이는 소수점 차이로 1~2등이 갈리는 질의(예: 카카오/카카오뱅크)에 긍정적 영향을 주었으며, 전체 정확도를 향상시켰습니다.

마지막으로 사전 기반 접근과 벡터 검색도 고려했지만 배제했습니다. 사전은 키워드 변화와 동의어 관리의 복잡성 때문에 유지보수가 어렵다고 판단했고, 벡터 검색은 과제 범위에 비해 오버스펙이라고 보아 제외했습니다.


### 의사 결정 근거
- 아키텍처 선택
  - 단순 계층형 구조는 외부 연동과 문서 타입 확장이 늘어날수록 유지보수가 어려움.
  - 핵심 로직을 외부 인프라(DB, API 등)와 분리하고 인터페이스(포트)로만 연결하도록 설계.
  - 다양한 어댑터를 조합해 독립적인 파이프라인을 구성할 수 있어 확장성과 변경 용이성 확보 -> 헥사고날 아키텍처 선택.
- 문서 타입별 처리 방식
  - TSV(QnA)
    - 문서 특성상 공통 필드 강제가 무의미하므로 question과 answer만 추출.
  - HTML(위키)
    - 인포박스·요약·본문을 분리해 필드화, 이후 검색 시 각기 다른 가중치를 부여.
  - 타입별 특성을 존중하는 구조로 설계해 단순하면서도 효율적인 색인 구조 확보.
- published 필드 활용
  - TSV
    - published=false 문서를 색인하지 않고 검색 옵션에서도 제거
  - HTML
    - published=true를 기본값으로 설정하되, 운영 제재/차단 대응을 위해 필드 유지 -> 운영상 유연성 확보.
- HTML 문서 파싱 전략
  - 문서 구조가 다양해 템플릿 기반 접근이 어려움 -> 불필요한 태그 제거 후 의미 있는 본문 추출.
  - 인포박스와 요약은 별도 필드로 분리해 가중치 부여.
  - 일부 데이터 품질 이슈(소수점 자리수 보정)도 변환 과정에서 처리 -> 구조적 다양성과 품질 문제를 동시에 해결.
- 검색 랭킹 튜닝
  - TSV
    - question과 answer에 동일 가중치 적용, ngram/BM25 파라미터/품사 제거 등은 일부 질의에만 효과적이어서 배제.
  - HTML
    - 인포박스/요약/title에 높은 가중치, 추가로 텍스트 길이를 정규화한 feature를 function_score에 반영 -> 소수점 차이로 갈리는 질의의 순위를 안정적으로 보정. 
    - 단순하고 안정적인 튜닝을 통해 전체 정답률 최적화
- 배제한 접근 방식
  - 사전 기반 검색
    - 키워드 변동성과 동의어 관리 문제로 유지보수 어려움.
  - 벡터 검색
    - 과제 범위 대비 오버스펙으로 판단, BM25 기반 보정으로 충분한 성능 확보 가능. -> 과제 범위와 실용성을 고려해 현실적인 선택.