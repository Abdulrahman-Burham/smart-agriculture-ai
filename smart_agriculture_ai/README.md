# Smart Agriculture AI

A modular Python project scaffold for an Arabic agricultural RAG assistant designed for Egyptian farmers. The system is built around grounded retrieval-augmented generation for crop disease advice, irrigation guidance, fertilization support, and treatment protocols.

## Purpose

This project provides a clean foundation for a text-only agricultural AI assistant that:

- answers in Egyptian farming Arabic
- understands Arabic and English mixed inputs
- uses crop and disease metadata from a separate vision model
- retrieves relevant knowledge chunks from a curated agriculture knowledge base
- grounds responses in retrieved context
- flags low-confidence or risky recommendations for agronomist review

## Architecture

The pipeline is organized as follows:

1. Preprocessing: normalize Arabic queries, map dialect terms to canonical agricultural language, and detect user intent.
2. Ingestion: load text documents, split into semantically meaningful chunks, and store them in Chroma plus BM25.
3. Retrieval: run hybrid vector + BM25 search using LangChain's EnsembleRetriever patterns.
4. Reranking: filter candidates by metadata and keep the strongest top-k context chunks.
5. Generation: build a grounded prompt and call the configured LLM provider.
6. Response: check confidence, log outputs, and flag review requirements when needed.

## Project layout

```text
smart_agriculture_ai/
  app/
  config/
  rag/
  services/
  utils/
  tests/
  requirements.txt
  README.md
  .env.example
```

## Configuration

Settings are managed centrally in `config/settings.py` and environment variables are defined in `.env.example`.

You can configure:

- embedding model
- LLM provider and model
- vector store type
- BM25 settings
- retrieval weights
- confidence threshold
- region/crop filters
- environment name

## Key modules

- `rag/preprocess.py`: Arabic query normalization, lexicon handling, intent detection, and fallback rewrite hooks.
- `rag/ingest.py`: text-only ingestion, chunking, metadata handling, and index creation.
- `rag/retrieve.py`: hybrid retrieval with vector + BM25 fusion.
- `rag/rerank.py`: metadata filtering and reranking before context assembly.
- `rag/generate.py`: prompt building and grounded generation.
- `rag/respond.py`: confidence evaluation and final response logging.

## Notes

- OCR and paper-document parsing are intentionally not included.
- The project uses Chroma for local/dev examples and keeps the abstraction ready for a Pinecone transition.
- The LLM provider is swappable through config and service-layer abstraction.
- This scaffold is intentionally simple and modular rather than production-hardening heavy.

## Getting started

1. Create a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in the environment variables.
4. Run the tests:
   ```bash
   pytest
   ```

## Future work

- populate the lexicon with agronomist-reviewed Arabic terms
- add a real vector-store implementation for Chroma/Pinecone
- integrate a hosted or local LLM provider
- ingest curated agriculture guides and protocol documents
- add retrieval evaluation and hallucination checks
