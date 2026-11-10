FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY prompt ./prompt

RUN useradd -m -u 10001 agente && mkdir -p /data && chown agente /data
USER agente

CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8090", "--workers", "1"]
