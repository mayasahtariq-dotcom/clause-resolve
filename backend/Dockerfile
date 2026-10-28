# syntax=docker/dockerfile:1
# ClauseLens API / worker image. Same image runs both roles:
#   API:    uvicorn (default CMD)
#   Worker: celery -A clauselens.worker worker -Q investigations
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY pyproject.toml ./
COPY clauselens ./clauselens
# Optional: behind a TLS-intercepting proxy, pass its CA without baking it into the image:
#   docker build --secret id=extra_ca,src=/path/to/ca.pem .
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; \
    pip install ".[celery]"

COPY alembic.ini ./
COPY alembic ./alembic

RUN useradd --create-home --uid 10001 clauselens
USER clauselens

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn clauselens.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
