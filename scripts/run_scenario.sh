#!/usr/bin/env bash
python report_app/app/reporter.py \
    --mode run_api \
    --answer_file report_app/resources/data/report.tsv \
    --count 3 \
    --api_url http://localhost:8000
