FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY proxy /app/proxy

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

EXPOSE 8080

ENV HOST=0.0.0.0
ENV PORT=8080
ENV DATA_DIR=/app/data
ENV USAGE_DB_PATH=/app/data/usage.sqlite
ENV AUDIT_LOG_PATH=/app/data/audit.jsonl

CMD ["python", "-m", "uvicorn", "proxy.main:app", "--host", "0.0.0.0", "--port", "8080"]
