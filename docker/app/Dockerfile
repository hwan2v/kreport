FROM python:3.11-slim

WORKDIR /kreport
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api_server /kreport/api_server
RUN mkdir -p /var/log/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/kreport
EXPOSE 8000

CMD ["uvicorn", "api_server.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
