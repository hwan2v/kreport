import os
import logging
import sys
import json
import time
import argparse
from typing import Dict, List, Union, Any
from urllib.parse import urlparse
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import traceback
import csv
import httpx
import asyncio


logger = logging.getLogger(__name__)

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
        # Reuse a single HTTP session for connection pooling/keep-alive
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({"Connection": "keep-alive"})
    
    
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
            for row in reader:
                if len(row) > 3:
                    continue
                no = int(row[0].strip())
                question = row[1].strip()
                answer = row[2].strip() if len(row) > 2 else ""
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
                f"{self.api_url}/api/search",
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

    
    def report(self, answer_dict: Dict[int, str], search_dict: Dict[int, Dict[str, Any]], output_file_path: str = None):
        def sanitize(v: Any, keep_newlines: bool = True) -> str:
            """TSV 안전화를 위한 전처리: 탭 제거, (선택) 개행 유지/제거."""
            if v is None:
                return ""
            s = str(v)
            s = s.replace("\t", " ")  # 탭은 반드시 공백으로
            if keep_newlines:
                # 개행은 셀 내부 줄바꿈으로 남김 (Excel에서도 한 셀로 보임)
                return s
            else:
                # 행 밀림이 싫고, 한 줄로만 보이길 원하면 개행 제거
                return s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

        true_count = 0
        total_search_time = 0.0
        report_file_path = output_file_path if output_file_path else self.answer_file.replace('.tsv', '_result.tsv')

        # Excel 친화: utf-8-sig + newline='' + CRLF
        with open(report_file_path, 'w', encoding='utf-8-sig', newline='') as wf:
            writer = csv.writer(
                wf,
                delimiter="\t",
                lineterminator="\r\n",   # CRLF
                quotechar='"',
                escapechar="\\",
                doublequote=True
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
                    sanitize(no, keep_newlines=False),             # 번호는 개행 불필요
                    sanitize(question, keep_newlines=True),        # 긴 텍스트는 셀 내 줄바꿈 허용
                    sanitize(answer, keep_newlines=True),
                    sanitize(result_1, keep_newlines=True),
                    sanitize(result_2, keep_newlines=True),
                    sanitize(result_3, keep_newlines=True),
                    sanitize(is_contain_answer, keep_newlines=False),
                    sanitize(search_time, keep_newlines=False),
                ])

            avg = (total_search_time / max(len(answer_dict), 1))
            writer.writerow([
                "최종결과", "", "", "", "", "",
                sanitize(true_count, keep_newlines=False),
                sanitize(avg, keep_newlines=False),
            ])



    def report_old(self, answer_dict: dict, search_dict: dict, output_file_path: str = None):
        true_count = 0
        total_search_time = 0
        report_file_path = output_file_path if output_file_path else self.answer_file.replace('.tsv', '_result.tsv')
        with open(report_file_path, 'w', encoding='utf-8') as wf:
            wf.write('\t질문\t필수 포함 text\t검색된 text 1\t검색된 text 2\t검색된 text 3\t정답 포함 여부\t속도\n')
            for no, answer_obj in answer_dict.items():
                question = answer_obj["question"]
                answer = answer_obj["answer"]
                search_result = search_dict[no]["search_result"]
                search_time = search_dict[no]["search_time"]
                parsed_search_results = self._parse_search_result(search_result)
                is_contain_answer = "true" if len(parsed_search_results) > 0 and answer in parsed_search_results[0] else "false"
                true_count += 1 if is_contain_answer == "true" else 0
                total_search_time += search_time
                result_1 = parsed_search_results[0] if len(parsed_search_results) > 0 else ""
                result_2 = parsed_search_results[1] if len(parsed_search_results) > 1 else ""
                result_3 = parsed_search_results[2] if len(parsed_search_results) > 2 else ""
                wf.write(f'{no}\t{question}\t{answer}\t{result_1}\t{result_2}\t{result_3}\t{is_contain_answer}\t{search_time}\n')
            average_search_time = total_search_time / len(answer_dict)
            wf.write(f"최종결과\t\t\t\t\t\t{true_count}\t{average_search_time}\n")


    def _parse_search_result(self, search_result):
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
            
    def _build_query(self, question: str, size: int = 3):
        body = {
            "size": size,
            "query": {
                "multi_match": {
                    "query": question,
                    "fields": ["title", "body"],
                    "type": "best_fields",
                    "operator": "or"
                }
            }
        }
        return body
    
    async def call_api(self, client: httpx.AsyncClient, url: str, q: str, size: int = 3) -> dict:
        """단일 호출 + 예외 처리 + 상태코드 체크"""
        r = await client.post(f"{url}/api/search", json={"query": q, "size": size}, timeout=10)
        r.raise_for_status()
        return r.json()
    
    async def search_answers_async(self, answer_dict: dict, max_concurrency: int = 20) -> dict:
        async with httpx.AsyncClient() as client:
            tasks = [self.call_api(client, self.api_url, obj["question"]) for no, obj in answer_dict.items()]
            results = await asyncio.gather(*tasks)
        return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
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
        default='http://localhost:8000',
        help='api url', 
        dest='api_url')

    args = parser.parse_args()
    try:
        logger.info(
            f"report start: answer_file={args.answer_file} count={args.count} api_url={args.api_url}"
        )
        
        search_report = SearchReport(
            answer_file=args.answer_file,
            count=args.count,
            api_url=args.api_url
        )
        
        # 질문 파일 초기화
        answer_dict = search_report.init_answer_file()
        # 질문 검색
        search_dict = search_report.search_answers(answer_dict)
        #search_dict = asyncio.run(
        #    search_report.search_answers_async(answer_dict, max_concurrency=20)
        #)
        # 리포트 생성
        search_report.report_old(answer_dict, search_dict)
        # close session
        search_report.close()
        
        logger.info(f"report success: {args.answer_file}")
    except Exception as e:
        logger.error(f"failed to report: {e}")
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)
