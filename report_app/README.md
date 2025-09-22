# Report App

## 1. 프로젝트 개요
이 앱은 API 서버에서 생성된 인덱싱/검색 결과를 바탕으로 리포트를 생성하는 Python 스크립트입니다.  
최종 결과는 TSV 파일로 저장됩니다.

- 입력: `report_app/resources/report.tsv`
- 출력: `report_app/resources/report.tsv`
- 주요 기능
  - `--mode clean`
    - 모든 인덱스 삭제
  - `--mode scenario`
    - API 호출 과정을 한번에 실행함
    - 다음 과정 실행
      - `데이터 추출 API(day_1,2,3) -> 변환 API(day_1,2,3) -> 적재 API(day_1,2,3) -> 검색 API -> 최종 결과 저장 `
  - `--mode report`
    - 최종 결과 리포트 생성
    - `report.tsv 파일 조회 -> 검색 API -> 최종 결과 저장` 과정 진행
  
## 2. 실행 방법
### docker 설치
- api_server/README.md 참고

### python 설치(로컬 실행시)
```bash
# macOS
brew update
brew install python@3.11
python3.11 --version


# Ubuntu / Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 --version
```

### 로컬 실행
```bash

python -m pip install -r requirements.txt

# 리포트 생성
python report_app/app/reporter.py --mode report --api_url http://localhost:8000 --opensearch_url http://localhost:9200


# 시나리오 실행(API 호출 과정 한번에 실행)
python report_app/app/reporter.py --mode scenario --api_url http://localhost:8000 --opensearch_url http://localhost:9200
```

### 컨테이너 실행
```bash
docker exec -it kreport-python-1 bash

# 리포트 생성
python report_app/app/reporter.py --mode report --api_url http://k-api:8000 --opensearch_url http://opensearch:9200


# 시나리오 실행(API 호출 과정 한번에 실행)
python report_app/app/reporter.py --mode scenario --api_url http://k-api:8000 --opensearch_url http://opensearch:9200
```

## 3. 프로젝트 구조
```
report_app/
├── app
│   └── reporter.py        # 메인 스크립트
├── resources
│   ├── data               # 입력 데이터 및 출력 결과
└── README.md
```
## 4. 풀이 방법 및 의사 결정 근거
### 과제 해석
- API 서버의 추출/변환/색인 결과를 활용해 리포트를 생성하는 것이 목적이고,
- tsv 파일에 결과만 추가하면 되는 단순한 스크립트가 필요했고,
- 응답 속도를 측정하기 위해 호출단에서도 최적의 호출방식이 필요해보였습니다.

### 접근 방법
tsv를 순차적으로 읽고 검색 API를 호출하는 방식을 고려했으나 서버 연결을 매번 해야해서 응답 속도 지연이 발생했습니다. 그래서 session으로 커넥션 풀을 만들어 keep-alive로 연결을 유지하고 재사용하니 속도 개선이 되었습니다.
다만 동기 방식으로 요청하다보니 전체 처리 속도는 7-8초 가량 소요되었고,
이를 해결하기 위해 httpx를 이용하여 비동기로 호출했더니 전체 처리 속도가 1-2초로 크게 감소했습니다.
그러나.. 단일 호출은 비동기가 0.4-0.5정도 소요되었고, 동기 호출이 0.05정도 소요되어, 평균 응답 속도를 고려해서 동기방식으로 호출하도록 수정했습니다

원래 의도인 리포트만 생성하다보니 전처리 작업(추출, 변환, 적재)을 따로해야해서 테스트에 시간이 좀 소요되었습니다. 그래서 이 과정도 한번에 할 수 있도록 클래스를 생성했고, 리포트 생성과 분리하여 호출할 수 있도록 구조를 변경했습니다.

### 의사 결정
- requests.session으로 커넥션 풀을 만들고 커넥션 유지하여 호출 속도 개선
- 동기 방식(requests)으로 호출하여 단일/평균 응답 속도 제고
- 단일 스크립트 구조에서 args로 요청 분기(ex. report, scenario)
