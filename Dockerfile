# Multi-stage production Dockerfile for Egyptian Agriculture AI Platform Gateway

# Stage 1: Build & Dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime Image
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONPATH=/app \
    PORT=8000 \
    PYTHONUNBUFFERED=1

COPY --from=builder /install /usr/local

COPY rag/ /app/rag/
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY requirements.txt /app/

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
