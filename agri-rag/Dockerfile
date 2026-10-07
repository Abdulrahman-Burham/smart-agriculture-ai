FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY agri_rag ./agri_rag
COPY config ./config
COPY data ./data
# Bake the embedding model into the image so cold start never downloads from the internet.
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('intfloat/multilingual-e5-base')"
RUN useradd -m app && mkdir -p /app/storage && chown -R app /app /models
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/healthz')"
CMD ["sh", "-c", "python -m agri_rag.cli ingest && python -m agri_rag.cli serve"]
