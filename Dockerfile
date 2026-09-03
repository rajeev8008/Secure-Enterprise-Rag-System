FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
COPY app/__init__.py app/__init__.py
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install .

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY sample_data ./sample_data

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/qdrant \
    && chown -R appuser:appuser /app /data/qdrant
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-8000}"]
