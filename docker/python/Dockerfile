FROM python:3.11.11-bookworm
WORKDIR /kreport
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY report_app /kreport/report_app
COPY docker/python/run_scenario.sh /kreport/run_scenario.sh
RUN chmod +x /kreport/run_scenario.sh
COPY docker/python/run_report.sh /kreport/run_report.sh
RUN chmod +x /kreport/run_report.sh
RUN sed -i 's/\r$//' /kreport/run_scenario.sh /kreport/run_report.sh

ENV PYTHONUNBUFFERED=1
CMD ["tail","-f","/dev/null"]  
