FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Prague

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r supl && useradd -r -g supl -d /app supl

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY config.yaml /app/config.yaml

RUN mkdir -p /app/data /app/logs /app/watch_exports \
    && chown -R supl:supl /app

USER supl

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/schedule', timeout=3)" || exit 1

CMD ["python", "-m", "app", "serve", "--host", "0.0.0.0", "--port", "8000"]
