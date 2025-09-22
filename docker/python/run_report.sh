#!/bin/bash
python report_app/app/reporter.py --mode report --answer_file report_app/resources/data/report.tsv --count 3 --api_url http://k-api:8000 --opensearch_url http://opensearch:9200
