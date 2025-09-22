import os
import sys
import json
import time
import argparse
import requests
import re
import traceback
import csv
import httpx
import asyncio
from typing import Dict, List, Union, Any
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse
from urllib3.util.retry import Retry


retry = Retry(
    total=3,
    backoff_factor=0.3,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET", "POST"),
)
adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)

COLUMN_COUNT_MIN = 2

class PipelineClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.mount(base_url, adapter)
        self.session.headers.update({
            "Connection": "keep-alive",
            "Content-Type": "application/json"
        })

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    def _post(self, endpoint: str, payload: dict):
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Request failed for {url}: {e}")
            return None

    def run_pipeline(self, date: str):
        payload = {"date": date}

        print(f"day={date} Extract 단계 실행...")
        extract_result = self._post("/v1/extract", payload)
        if not extract_result:
            return {"error": "extract 실패"}

        print(f"day={date} Transform 단계 실행...")
        transform_result = self._post("/v1/transform", payload)
        if not transform_result:
            return {"error": "transform 실패"}

        print(f"day={date} Index 단계 실행...")
        index_result = self._post("/v1/index", payload)
        if not index_result:
            return {"error": "index 실패"}

        # 결과 합치기
        return {
            "extract": extract_result,
            "transform": transform_result,
            "index": index_result
        }


class SearchReport:
    def __init__(
        self, 
        answer_file: str, 
        count: int, 
        api_url: str
    ):
        self.answer_file = answer_file
        self.count = count
        self.api_url = api_url
        self.answer_dict = {}
        self.session = requests.Session()
        self.session.headers.update({
            "Connection": "keep-alive",
            "Content-Type": "application/json"
        })
        self.session.mount(self.api_url, adapter)
        try:
            self.session.get(f"{self.api_url}/v1/health", timeout=3)
        except Exception:
            pass
    
    
    def init_answer_file(self, answer_file_path: str = None):
        """
        질문
        필수 포함 text
        검색된 text 1	검색된 text 2	검색된 text 3	정답 포함 여부	속도
        1
        지구의 평균 반경은 얼마인가요?
        지구의 평균 반경은 약 6,371km입니다.
        """
        answer_dict = {}
        input_file_path = answer_file_path if answer_file_path else self.answer_file
        with open(input_file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader)
            rows = list(reader)
            for row in rows[:-1]:
                no = int(row[0].strip())
                question = row[1].strip()
                answer = row[2].strip() if len(row) > COLUMN_COUNT_MIN else ""
                answer_dict[no] = {
                    "question": question,
                    "answer": answer
                }
        return answer_dict
    
    def search_answers(self, answer_dict: dict):
        search_dict = {}
        for no, report_obj in answer_dict.items():
            question = report_obj["question"]
            answer = report_obj["answer"]
            start_time = datetime.now()
            response = self.session.post(
                f"{self.api_url}/v1/search",
                json={"query": question, "size": self.count},
                timeout=10,
            )
            search_result = response.json()["data"]
            search_time = (datetime.now() - start_time).total_seconds()
            search_dict[no] = {
                "search_result": search_result,
                "search_time": search_time
            }
        return search_dict

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    
    def sanitize(
        self, 
        v: Any, 
        keep_newlines: bool = True, 
        max_len: int | None = None, 
        soft_wrap_every: int | None = None) -> str:
        """
        TSV 안전화를 위한 전처리:
        - 탭 제거
        - (옵션) 개행 유지/제거
        - (옵션) 길이 제한
        - (옵션) 소프트 래핑(제로폭 공백 주입)으로 엑셀에서 줄바꿈 유도
        """
        if v is None:
            s = ""
        else:
            s = str(v)

        # 탭은 반드시 공백으로 치환(구분자 깨짐 방지)
        s = s.replace("\t", " ")

        if not keep_newlines:
            s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

        if max_len is not None and len(s) > max_len:
            s = s[:max_len] + "…"

        if soft_wrap_every:
            # 연속 긴 문자열 줄바꿈 유도(제로폭 공백 삽입)
            ZWSP = "\u200b"
            s = "".join(
                ch + (ZWSP if (i + 1) % soft_wrap_every == 0 else "")
                for i, ch in enumerate(s)
            )

        return s
        
    def report_v1(
        self, 
        answer_dict: Dict[int, str], 
        search_dict: Dict[int, Dict[str, Any]], 
        output_file_path: str = None):
        true_count = 0
        total_search_time = 0.0
        report_file_path = output_file_path if output_file_path else self.answer_file.replace('.tsv', '_result.tsv')

        # Excel 친화: utf-8-sig + newline='' + CRLF
        with open(report_file_path, 'w', encoding='utf-8-sig', newline='') as wf:
            writer = csv.writer(
                wf,
                delimiter="\t",
                lineterminator="\r\n",
                quotechar='"',
                escapechar="\\",
                doublequote=False
            )

            # 헤더
            writer.writerow(["", "질문", "필수 포함 text", "검색된 text 1", "검색된 text 2", "검색된 text 3", "정답 포함 여부", "속도"])

            for no, answer_obj in answer_dict.items():
                question = answer_obj.get("question", "")
                answer = answer_obj.get("answer", "")
                search_result = search_dict[no]["search_result"]
                search_time = search_dict[no]["search_time"]
                parsed_search_results = self._parse_search_result(search_result)

                is_contain_answer = (
                    "true"
                    if (len(parsed_search_results) > 0 and answer in parsed_search_results[0])
                    else "false"
                )
                if is_contain_answer == "true":
                    true_count += 1
                total_search_time += float(search_time)

                result_1 = parsed_search_results[0] if len(parsed_search_results) > 0 else ""
                result_2 = parsed_search_results[1] if len(parsed_search_results) > 1 else ""
                result_3 = parsed_search_results[2] if len(parsed_search_results) > 2 else ""

                writer.writerow([
                    self.sanitize(no, keep_newlines=False),
                    self.sanitize(question, keep_newlines=True, soft_wrap_every=80, max_len=4000),
                    self.sanitize(answer, keep_newlines=True, soft_wrap_every=80, max_len=4000),
                    self.sanitize(result_1, keep_newlines=True, soft_wrap_every=80, max_len=4000),
                    self.sanitize(result_2, keep_newlines=True, soft_wrap_every=80, max_len=4000),
                    self.sanitize(result_3, keep_newlines=True, soft_wrap_every=80, max_len=4000),
                    self.sanitize(is_contain_answer, keep_newlines=False),
                    self.sanitize(search_time, keep_newlines=False),
                ])

            avg = (total_search_time / max(len(answer_dict), 1))
            writer.writerow([
                "최종결과", "", "", "", "", "",
                self.sanitize(true_count, keep_newlines=False),
                self.sanitize(avg, keep_newlines=False),
            ])
        self._move_file(report_file_path, self.answer_file)
    
    def _move_file(self, source_file_path: str, target_file_path: str):
        if os.path.exists(target_file_path):
            os.remove(target_file_path)
        os.rename(source_file_path, target_file_path)
    
    def _parse_search_result(self, search_result: Dict[str, Any]) -> List[str]:
        result = []
        hits = search_result["hits"]["hits"]
        for hit in hits:
            hit_dict = hit["_source"]
            contents = []
            for key in ['title', 'body', 'summary', 'question', 'answer']:
                if key in hit_dict and hit_dict[key] is not None:
                    contents.append(hit_dict[key].replace("\n", " "))
            result.append(" ".join(contents))
        return result
    
    async def call_api(self, client: httpx.AsyncClient, url: str, q: str, size: int = 3) -> dict:
        """단일 호출 + 예외 처리 + 상태코드 체크"""
        start_time = datetime.now()
        r = await client.post(f"{url}/v1/search", json={"query": q, "size": size}, timeout=10)
        elapsed = (datetime.now() - start_time).total_seconds()
        r.raise_for_status()
        return {
            "json": r.json(),
            "elapsed": elapsed
        }
    
    async def search_answers_async(self, answer_dict: dict, max_concurrency: int = 20) -> dict:
        async with httpx.AsyncClient() as client:
            tasks = [self.call_api(client, self.api_url, obj["question"]) for no, obj in answer_dict.items()]
            results = await asyncio.gather(*tasks)
        search_dict = {}
        for no, response in enumerate(results):
            no = no + 1
            search_result = response['json']['data']
            search_dict[no] = {
                "search_result": search_result,
                "search_time": response['elapsed']
            }
        return search_dict

def run_report(args):
    search_report = SearchReport(
        answer_file=args.answer_file,
        count=args.count,
        api_url=args.api_url)
    
    # 질문 파일 초기화
    answer_dict = search_report.init_answer_file()
    # 질문 검색
    search_dict = search_report.search_answers(answer_dict)
    #search_dict = asyncio.run(
    #    search_report.search_answers_async(answer_dict, max_concurrency=20)
    #)
    # 리포트 생성
    search_report.report_v1(answer_dict, search_dict)
    # close session
    search_report.close()
    
    print(f"report success: {args.answer_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--mode',
        '-m', 
        help='execution mode \
            (clean: clean index, \
            report: generate report, \
            scenario: run api according to scenario)',
        choices=['clean', 'report', 'scenario'],
        default='report',
        dest='mode')
    parser.add_argument(
        '--answer_file', 
        '-a',
        help='answer file path(example: report_app/resources/data/report.tsv)',
        default='report_app/resources/data/report.tsv',
        dest='answer_file')
    parser.add_argument(
        '--count', 
        '-c',
        default=3,
        help='count for answer', 
        dest='count')
    parser.add_argument(
        '--api_url', 
        '-u',
        default='http://k-api:8000',
        help='api url', 
        dest='api_url')
    parser.add_argument(
        '--opensearch_url', 
        '-o',
        default='http://opensearch:9200',
        help='opensearch url', 
        dest='opensearch_url')


    try:
        args = parser.parse_args()
        print(
            f"report start: mode={args.mode} \
            answer_file={args.answer_file} \
            count={args.count} \
            api_url={args.api_url} \
            opensearch_url={args.opensearch_url}"
        )

        if args.mode == 'clean':
            res = requests.delete(f"{args.opensearch_url}/collection-*")
            res.raise_for_status()
            print(f"clean index success: {res.text}")

        elif args.mode == 'scenario':
            pipeline_client = PipelineClient(base_url=args.api_url)
            pipeline_client.run_pipeline(date="1")
            pipeline_client.run_pipeline(date="2")
            pipeline_client.run_pipeline(date="3")
            pipeline_client.close()
            time.sleep(3)
            print("검색&리포트 단계 실행...")
            run_report(args)

        elif args.mode == 'report':
            start_time = datetime.now()
            run_report(args)
            end_time = datetime.now()
            print(f"report success: time={(end_time - start_time).total_seconds()} seconds")
    except Exception as e:
        print(f'error: {e}')
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)
