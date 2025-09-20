import os
import logging
import sys
import json
import time
import argparse
from typing import Dict, List, Union
from urllib.parse import urlparse
from datetime import datetime
import traceback
import csv
from opensearchpy import OpenSearch, helpers


logger = logging.getLogger(__name__)

class SearchReport:
    def __init__(
        self, 
        answer_file: str, 
        count: int, 
        opensearch: OpenSearch,
        alias_name: str
    ):
        self.answer_file = answer_file
        self.count = count
        self.os = os
        self.alias_name = alias_name
        self.opensearch = opensearch
        self.answer_dict = {}
    
    
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
        with open(input_file_path, "r", encoding="utf-8") as f:
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
            body = self._build_query(question, self.count)
            start_time = datetime.now()
            search_result = self.opensearch.search(index=self.alias_name, body=body)
            search_time = (datetime.now() - start_time).total_seconds()
            search_dict[no] = {
                "search_result": search_result,
                "search_time": search_time
            }
        return search_dict

    
    def report(self, answer_dict: dict, search_dict: dict, output_file_path: str = None):
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
            wf.write(f'정답 개수: {len(answer_dict)}\n')
            wf.write(f'정답 포함 검색 개수: {true_count}\n')
            wf.write(f'평균 속도(sec): {average_search_time}\n')

    def _parse_search_result(self, search_result):
        result = []
        hits = search_result["hits"]["hits"]
        for hit in hits:
            hit_dict = hit["_source"]
            result.append(hit_dict["body"])
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
        '--alias_name', 
        '-n',
        default='kakaobank',
        help='alias name for opensearch', 
        dest='alias_name')
    parser.add_argument(
        '--opensearch_host', 
        '-o',
        default='http://localhost:9200',
        help='opensearch host', 
        dest='opensearch_host')

    args = parser.parse_args()
    try:
        logger.info(
            f"report start: answer_file={args.answer_file} count={args.count} alias_name={args.alias_name} opensearch_host={args.opensearch_host}"
        )
        
        u = urlparse(args.opensearch_host)
        opensearch = OpenSearch(
            hosts=[{"host": u.hostname, "port": u.port or 9200, "scheme": u.scheme or "http"}],
            verify_certs=False,
        )
        
        search_report = SearchReport(
            answer_file=args.answer_file,
            count=args.count,
            opensearch=opensearch,
            alias_name=args.alias_name
        )
        
        # 질문 파일 초기화
        answer_dict = search_report.init_answer_file()
        # 질문 검색
        search_dict = search_report.search_answers(answer_dict)
        # 리포트 생성
        search_report.report(answer_dict, search_dict)
        
        logger.info(f"report success: {args.answer_file}")
    except Exception as e:
        logger.error(f"failed to report: {e}")
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)
