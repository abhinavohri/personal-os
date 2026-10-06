FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY apps ./apps

USER 65532:65532
CMD ["sh", "-c", "uvicorn apps.uploader.main:app --host 0.0.0.0 --port ${PORT}"]
