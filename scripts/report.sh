#!/usr/bin/env bash
python report_app/app/reporter.py \
    --answer_file report_app/resources/data/report.tsv \
    --count 3 \
    --alias_name kakaobank \
    --opensearch_host http://localhost:9200
