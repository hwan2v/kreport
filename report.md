#### 버전
opensearch 2.17.1
python 3.11




## 초기 설정


```
# wsl ubuntu

sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p || true
```

# 문제
## 2-1 문제 요약
- 목적
  - 텍스트 검색 서비스에 필요한 기능을 제공하는 프로개름 개발.
- 문제1
  - 제공된 문서들을 순차적으로 수집하여 검새할 수 있는 형태로 가공하여
- 문제2
  - oepnsearch에 적재하고,
- 문제3
  - 적재된 문서들을 바탕으로 검색할 수 있는 api 서버와
- 문제4
  - 검색 결과 report(tsv)를 제공하는 프로그램을 python으로 개발한다.
## 2-1 report 참고
input/output은 
report_app/resources/data/report.tsv에 질문과 필수포함text를 참고.

## 2-2 적재문서 설명
### 수집날짜
- 적재된 문서를 수집 날짜에 맞춰 순차적으로 수집한다.
### html문서
### tsv 문서.
id 문서식별값(유니크값)
question 질문
answer 답변.
published 질/답 공개여부
user_id 질문한사람의 id

## 2-3 과제제출 참고 사항.
1. 첨부된 프로젝트 구조를 참고하여 과제물을 제출해줘.
2. opensearch 2.17.1, python 3.11 버전 사용하여 과제 구성.
3. 과제 실행 환경은 "외부와 격리된 환경"에서 실행(외부 api, 서비스 사용 불가함)
4. 첨부된 프로젝트의 README.md에 과제 실행 방법과, 과제 구성, 풀이 방법과 의사 결정의 근거 등을 포함해줘.
5. 아래 사항 고려해서 개발해.
a. 객체지향으로 개발
b. 단위/통합 테스트 코드 작성.하고 결과 확인가능해야함
c. docstring, typing, comment 최대한 활용
d. runtimerror등 예외 상화을 고려해 작성(exception handling)

# 과제
## 3-1 문제1.
원천 데이터 추출하여 "검색에 적합한 형태로 가공하고, json 형태로 정해진 로컬 파일 시스템에 저장하는 api 서버 개발"

요구 사항 
1. json 파일 경로 api_server/resources/data/json/(html/tsv)/day_(1,2,3) 
2. 순차적 데이터 수집 
○ API 호출 파라미터에 수집 날짜를 추가하여 순차적으로 수집을 진행합니다. 
○ 첫 번째 데이터 수집은 day 1 디렉토리의 데이터 입니다. 
○ 첫 번째 데이터 수집 이후, day 2, 3이 지나며 주어진 데이터 파일에 변경 사항(추가, 수정, 삭제)이 
발생합니다. 
■ 추가: 기존 데이터에 없던 새로운 데이터가 추가됨. 
■ 수정: 기존 데이터가 업데이트됨. 
■ 삭제: 기존 데이터가 삭제됨. 
3. 원천 데이터 추출 및 JSON 형식으로 저장 
○ 원천 데이터를 추출하여 검색하기 적합한 형태로 데이터를 가공한 후, JSON 형태로 지정된 파일 
경로에 저장합니다. 
4. 문서의 분할 저장 
○ 길이가 긴 문서의 경우, 검색 속도 및 품질을 고려하여 다양한 청킹 방식을 통해 문서를 나누어 
저장합니다. 
5. 저장되는 데이터의 필수 정보 
○ 공통 정보: 
■ 원천 데이터 고유 아이디 (source_id) 
■ 원천 데이터 경로 (source_path) 
■ 원천 데이터 파일 타입 (file_type) 
○ HTML  문서의 추가 정보: 
■ 문서 제목 (title) 
○ TSV 문서의 추가 정보: 
■ 질문 (question) 
■ 답변 (answer) 
■ 공개 여부 (published) 
○ 위 외에 검색 속도 및 품질을 고려한 기타 추가 정보는 자유롭게 구성합니다.


## 3-2. 문제#2 
문제#1에서 가공한 데이터를 OpenSearch에 적재하는 API를 추가 개발합니다. API 호출시 다음 요구 사항을 
충족해야 합니다.  
요구사항 
● 검색을 위해 필요한 opensearch index를 생성합니다. 
● local filesystem에 저장된 데이터를 생성한 opensearch index에 적재합니다. 
● API 호출 파라미터에 수집 날짜를 추가하여 순차적으로 데이터를 적재 및 수정/삭제 합니다. 

## 3-3. 문제#3 
OpenSearch index에 적재한 데이터를 텍스트로 검색하는 API를 추가 개발합니다. API 호출시 다음 
요구사항을 충족해야 합니다. 
요구사항 
● 검색 속도와 품질을 고려하여 제공된 질문에 맞는 문서를 검색할 수 있는 API를 구현합니다. 
● 검색 결과 문서의 개수(topK)는 3개로 고정합니다. 
3-4. 문제#4 
구현한 API서버를 활용하여 데이터 적재 API 호출부터 검색 API까지 각각의 API를 호출하여 최종 검색 결과 
report를 생성하는 프로그램을 구현합니다.  
요구사항 
● report 경로 : report_app/resources/data/report.tsv 
● report 내용  
○ 검색 품질 
■ 품질 측정 방식  
■ report파일의 모든 “질문” 대상으로 품질을 측정합니다. 
■ report파일에는 총 100개의 “질문”과 “필수 포함 text”가 제공됩니다. 
■ 각 질문을 검색 API에 요청하여 검색된 순서대로 report파일에 “검색된 
text”에 작성되도록 합니다.(문서 1,2,3은 score가 높은 순서대로 작성) 
■ report파일에 문서 id, type 등은 제거하고 실제 문서의 내용만 작성되면 
됩니다. 
■ “검색된 text 1”에 필수 포함 text가 포함된 경우 true, 포함되지 않으면 
false로 “정답 포함 여부” 셀에 작성되도록 합니다. 
○ 검색 속도  
■ 속도 측정 방식 
■ 질문 하나 당 단일 검색 쿼리 속도를 각각 측정합니다. 
■ 최종 결과(평균 속도) :  단일 검색 쿼리 속도의 합(초)/100(쿼리 개수)


## todo
금: 폴더 구조 정리, 색인 구조 변경, 테스트 코드 추가
토: 품질(파싱, 트랜스폼), 성능 추가, 셀러리 구조도 생각해보기(임베딩)
  과거문서 포함 추출? 색인 해야해?
  
일: 품질 개선, 테스트 코드 추가

월: 공통 코드 보완, 문서 작성
  14시까지 테스트 코드 보완 및 주석 추가

  18시까지 리포트, 도커 정리

  20시까지 사유, 문서 작성(실행 방법과 과제 구성, 풀이 방법과 의사 결정 근거등)

  24시까지 품질 개선 및 정리.

  02시 과제 제출! 
  빠진거 없는지 확인. 폴더. 에러 등.



역할 구분
Parse (파싱)
원천 포맷 → 내부 중간 스키마로 구조화
HTML: DOM 파서로 title, headings, body, links, lang? 추출
TSV/CSV: 컬럼 분리, 타입 캐스팅 시도(문자→숫자/날짜)
파일 메타: uri, etag, last_modified, size
결과: 원본에 충실한 최소 정보 + 표준 필드명
실패 기준: 문법 오류, 필수 필드 부재(= “읽을 수 없음”)
산출물: Raw/Parsed 모델 (예: ParsedHtml, ParsedQnaRow)

Transform (변환)
Parsed → 색인/검색/분석에 최적화
정제: 불필요 태그/스크립트 제거, 공백/이모지/제어문자 정리
정규화: 소문자화, 표기 통합(예: “k8s”↔“Kubernetes”), 토큰 정리
축약/분할: 본문을 문단/문장 chunk로 나누기, 길이 제한
파생 특성: all_text 생성(copy_to 대상), 키워드 필드, n-gram, 요약문
품질/검증: 길이/언어 필터, 금칙어/PII 마스킹
풍부화(enrichment): 키워드 태깅, 엔티티 인식, 카테고리, 중요도
임베딩: *_vec 계산 → kNN 색인용
결과: Index 모델 (예: IndexDocHtml, IndexDocQna)

왜 분리하나?
관심사 분리: “읽기 실패”와 “품질/정책 실패”를 구분 → 운영/리트라이 용이
재사용성: Parsed를 보존하면 다른 변환 파이프라인(요약/NER/임베딩) 재사용
테스트 용이: 파서는 포맷 안정성, 트랜스폼은 품질/랭킹 효과를 독립 검증
에러 정책(권장)
Parse 실패 → Hard fail (소스/포맷 이슈)
Transform 실패 → Soft fail (특정 enrichment만 건너뛰고 기본 색인은 진행)
상태 기록: manifest에 parsed_ok, transformed_ok, indexed_ok와 원인 로그


# 아이디어
### 파싱
html 파싱은 무엇으로하지? 어떤 것을 넣어야 검색이 잘되는걸가?
tsv는 제목, 답변, 날짜, 게시자 있음.

### 색인
색인을 api로만 받나? docker-compose에서 worker(celery)를 통해 주기적으로 호출하면 안돼?
배치?
색인이 일별로 있다는 것은 증분색인을 어떻게 할것인지를 보고 싶은것인가?
source_id : keyword
source_path : text
file_type : keyword
seq: integer
title : text
body : text
title_embedding: list
body_embedding: list
created_date : datetime
updated_date : datetime
author : keyword
published : boolean

  
### 확장성
k8s 기반의 메니페스트도 작성?
argo도 작성? 너무 오바야?
도커컴포즈로 모놀리식으로 제공하고, 리드미도 그렇게 하되, 개별로 설치하는 법?
불변리소스와 가변 리소스를 성능측정해서 guvicorn으로 하되 최적으로 할수있게 설정하고,
컨테이너로 확장할수 있게하자.
즉 글로벌로 있어야할 것은? 

### 로그
로그스태시로 처리할까? 비동기
```
mkdir -p logstash/pipeline
mkdir -p logs
```

### 보안
api-key를 발급받어?
opensearch ssl 적용해? 과연 필요할까?
다른 보안 사항없어?

### 속도
레디스로 짧게 캐싱해야할까?
속도가 빠른 키워드 매칭만 할까?
임베딩 벡터 매칭 필요없을까?
asyncio를 사용하여 최대한 빠른 응답되게할가?
locust로 속도 측정결과첨부할까?


### 품질
ndcg 넣어? 어떻게 해?
임베딩 벡터 매칭해야하나? 하이브리드 검색 되게 해? -> 속도를 봐야함
파싱에 달렸나?
어떤 필드를 넣어야 좀 더 정확한 결과가 매칭될가? -> 
가장 최신의 문서가 업데이트되어야하고, 최신의 문서가 검색되어야한다.

### 스키마
음.. 품질과 관련됨.
유의어 유사어 등 넣어야함?

### 디렉토리 구조 제안
```
app/
├─ api/
│  ├─ routers/
│  │  ├─ extract.py          # POST /extract  (얇게)
│  └─ deps.py                # 의존성 조립 (DI)
├─ domain/
│  ├─ models.py              # Collection/Document 엔티티
│  ├─ ports.py               # FetchPort/ParserPort
│  └─ services/
│     └─ search_service.py   # SearchService (유스케이스 오케스트레이션)
├─ infra/
│  ├─ fetchers/
│  │  └─ http_fetcher.py     # URL에서 HTML 가져오기
│  ├─ parsers/
│  │  ├─ bs4_parser.py       # HTML→문서들 파싱
│  │  └─ trafilatura_parser.py (옵션)
│  └─ repos/
│     └─ opensearch_collection_repo.py   # 컬렉션 저장 (OpenSearch/DB 등)
└─ main.py
```