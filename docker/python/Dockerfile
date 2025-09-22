FROM python:3.11.11-bookworm
WORKDIR /kreport
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY report_app /kreport/report_app

ENV PYTHONUNBUFFERED=1
CMD ["tail","-f","/dev/null"]  
